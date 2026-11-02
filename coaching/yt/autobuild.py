# -*- coding: utf-8 -*-
"""spec に "auto": ["illust", "build"] と書いてある動画を、VPS でデプロイ直後に自動で作る（チャットで台本を書いたときに使う）。
  deploy.sh から  nohup python3 coaching/yt/autobuild.py &  で呼ばれる。
  ほかの作業が動いていれば終わるまで待ち、スタジオの作業欄（current.json）に進み具合を出す。
"""
import json, os, shlex, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.dirname(os.path.dirname(HERE))
SPECS = os.path.join(HERE, "specs")
OUT = os.environ.get("YT_OUT", os.path.join(HERE, "out"))
JOBDIR = os.path.join(OUT, "_jobs"); CUR = os.path.join(JOBDIR, "current.json")
PY = sys.executable

def _alive(pid):
    try: os.kill(pid, 0); return True
    except OSError: return False

def busy():
    try: j = json.load(open(CUR))
    except Exception: return False
    return not os.path.exists(j["log"] + ".rc") and _alive(int(j["pid"]))

def env():
    e = dict(os.environ)
    kp = os.path.join(ROOT, ".google_api_key")
    if not e.get("GOOGLE_TTS_API_KEY") and os.path.exists(kp): e["GOOGLE_TTS_API_KEY"] = open(kp).read().strip()
    return e

def run(name, steps):
    p = os.path.join(SPECS, name + ".json")
    cmds = {"illust": [PY, "-u", "build_spec.py", p, "--illust", "0"], "draft": [PY, "-u", "build_spec.py", p, "--draft"], "build": [PY, "-u", "build_spec.py", p],
            "short": [PY, "-u", "shorts.py", p, "1"]}
    chain = " && ".join(shlex.join(cmds[s]) for s in steps if s in cmds)
    os.makedirs(JOBDIR, exist_ok=True)
    log = os.path.join(JOBDIR, "auto.log"); q = shlex.quote
    if os.path.exists(log + ".rc"): os.remove(log + ".rc")
    cmd = f"( {chain}; echo $? > {q(log + '.rc')} ) > {q(log)} 2>&1 < /dev/null & echo $!"
    r = subprocess.run(["sh", "-c", cmd], capture_output=True, text=True, env=env(), cwd=HERE, start_new_session=True)
    pid = int(r.stdout.strip())
    json.dump({"pid": pid, "name": name, "kind": "auto", "label": "자동 제작 (" + "→".join(steps) + ")", "log": log, "started": time.time()}, open(CUR, "w"))
    while _alive(pid) and not os.path.exists(log + ".rc"): time.sleep(10)      # 自分が始めた作業だけ待つ

def main():
    os.makedirs(JOBDIR, exist_ok=True)
    for f in sorted(os.listdir(SPECS)) if os.path.isdir(SPECS) else []:
        if not f.endswith(".json"): continue
        p = os.path.join(SPECS, f)
        try: sp = json.load(open(p, encoding="utf-8"))
        except Exception as e: print(f"{f}: 읽기 실패 → 건너뜀 ({e})", flush=True); continue
        steps = sp.get("auto")
        if not steps: continue
        sp.pop("auto"); sp["auto_done"] = time.strftime("%Y-%m-%d %H:%M")      # 二度始めないよう先に印を消す
        json.dump(sp, open(p + ".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(p + ".tmp", p)
        import fcntl                                                              # 自動制作どうしは同時に走らせない（デプロイのたびに1本ずつ起動されるため）
        lockf = open(os.path.join(JOBDIR, "autobuild.lock"), "w")
        for _ in range(720):
            try: fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB); break
            except OSError: time.sleep(10)
        for _ in range(360):                                                      # 最大1時間、ほかの作業が終わるのを待つ
            if not busy(): break
            time.sleep(10)
        print(time.strftime("%F %T"), f"자동 제작 대기 끝 (busy={busy()})", flush=True)
        print(f"자동 제작 시작: {sp['name']} {steps}", flush=True)
        try: run(sp["name"], steps)
        finally:
            try: fcntl.flock(lockf, fcntl.LOCK_UN); lockf.close()
            except Exception: pass

if __name__ == "__main__":
    main()
