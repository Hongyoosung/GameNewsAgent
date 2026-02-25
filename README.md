# GameNewsAgent
Build a local agent that researches and summarizes news about games, latest technology trends, etc. every morning and pushes them to a repository (with OpenClaw &amp; Qwen3-4b).

Target OS: Windows (with WSL2)

### Get Start
1. Set LLM (PowerShell, Windows):
```cmd
.\setup-llm.ps1
```

2. Install OpenClaw (WSL2 안에서 실행)
```cmd
wsl

# WSL 터미널 안에서
npm install -g openclaw@latest
openclaw onboard --install-daemon
```

3. Manual testing
   - **WSL 추천 (직접 실행)**:
```bash
bash scripts/run-daily.sh
```

   - **Windows PowerShell 에서 실행 (WSL 위임)**:
```cmd
.\run_daily.ps1
```


openclaw config set agents.defaults.model.primary "qwen-portal/vision-model"


