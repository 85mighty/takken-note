// PM2 설정 — VPS에서: pm2 startOrRestart ecosystem.config.js
// 이 파일은 수정하지 말 것 (git 관리 대상 — 수정하면 업데이트 때 pull이 막힘).
// 비밀번호는 같은 폴더의 .takken_password 파일에 넣는다 (git 무시 대상):
//   echo '원하는비밀번호' > .takken_password
const fs = require("fs");
const path = require("path");

let password = "";
try {
  password = fs.readFileSync(path.join(__dirname, ".takken_password"), "utf8").trim();
} catch (e) {}

// deploy.sh가 만든 .venv가 있으면 그쪽 파이썬 사용 (PEP 668 환경 대응)
const venvPython = path.join(__dirname, ".venv", "bin", "python3");
const interpreter = fs.existsSync(venvPython) ? venvPython : "python3";

module.exports = {
  apps: [
    {
      name: "takken-note",
      script: "app.py",
      interpreter: interpreter,
      cwd: __dirname,
      env: {
        HOST: "0.0.0.0",          // 외부(아이폰)에서 접속하려면 0.0.0.0
        PORT: "8788",
        TAKKEN_PASSWORD: password, // 비어 있으면 로그인 없이 전체 공개됨
      },
    },
  ],
};
