Write-Host "LLM 컨테이너를 백그라운드에서 실행합니다..."
docker-compose up -d ollama

Write-Host "모델 다운로드를 시작합니다 (약 5.2GB, 시간이 소요될 수 있습니다)..."
# Change 'ollama' to 'gna-ollama-1'
docker exec gna-ollama-1 ollama pull qwen3:8b

Write-Host "설정이 완료되었습니다!"