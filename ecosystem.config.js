// PM2 설정 — VPS에서: pm2 startOrRestart ecosystem.config.js
module.exports = {
  apps: [
    {
      name: "takken-note",
      script: "app.py",
      interpreter: "python3",
      cwd: __dirname,
      env: {
        HOST: "0.0.0.0",          // 외부(아이폰)에서 접속하려면 0.0.0.0
        PORT: "8788",
        TAKKEN_PASSWORD: "CHANGE_ME", // ← 반드시 바꿀 것. 비우면 로그인 없이 전체 공개됨
      },
    },
  ],
};
