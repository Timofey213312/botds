# Установка Lavalink для музыки Discord бота
Write-Host "Установка Lavalink для музыки Discord бота" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Проверка Java
Write-Host "Проверяем установку Java..." -ForegroundColor Yellow
try {
    java -version 2>&1 | Out-Null
    Write-Host "✅ Java установлена" -ForegroundColor Green
} catch {
    Write-Host "❌ Java не установлена!" -ForegroundColor Red
    Write-Host "Установите Java 17+ с официального сайта:" -ForegroundColor Yellow
    Write-Host "https://adoptium.net/" -ForegroundColor Blue
    pause
    exit 1
}

# Создаем папку для Lavalink
if (-Not (Test-Path "lavalink")) {
    New-Item -ItemType Directory -Path "lavalink" | Out-Null
}
Set-Location "lavalink"

# Скачиваем Lavalink
Write-Host "Скачиваем Lavalink..." -ForegroundColor Yellow
try {
    Invoke-WebRequest -Uri "https://github.com/lavalink-devs/Lavalink/releases/latest/download/Lavalink.jar" -OutFile "Lavalink.jar"
    Write-Host "✅ Lavalink скачан" -ForegroundColor Green
} catch {
    Write-Host "❌ Не удалось скачать Lavalink" -ForegroundColor Red
    Write-Host "Скачайте вручную с: https://github.com/lavalink-devs/Lavalink/releases" -ForegroundColor Yellow
    pause
    exit 1
}

# Создаем конфигурационный файл
Write-Host "Создаем конфигурационный файл..." -ForegroundColor Yellow
@"
server:
  port: 2333
  address: 127.0.0.1
lavalink:
  server:
    password: "youshallnotpass"
    sources:
      youtube: true
      bandcamp: true
      soundcloud: true
      twitch: true
      vimeo: true
      http: true
      local: false
metrics:
  prometheus:
    enabled: false
    endpoint: /metrics
sentry:
  dsn: ""
  environment: ""
logging:
  file:
    max-history: 30
    max-size: 1GB
  path: ./logs/
  level:
    root: INFO
    lavalink: INFO
"@ | Out-File -FilePath "application.yml" -Encoding UTF8

Write-Host "✅ Конфигурация создана" -ForegroundColor Green

Write-Host ""
Write-Host "📋 Инструкция по запуску:" -ForegroundColor Cyan
Write-Host "1. Перейдите в папку lavalink: cd lavalink" -ForegroundColor Yellow
Write-Host "2. Запустите Lavalink: java -jar Lavalink.jar" -ForegroundColor Yellow
Write-Host "3. Оставьте Lavalink работать в отдельном окне" -ForegroundColor Yellow
Write-Host "4. Запустите бота в другом окне: python main.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "⚠️ Примечание: Бот автоматически подключится к Lavalink" -ForegroundColor Magenta

pause