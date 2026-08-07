@echo off
echo Установка Lavalink для музыки Discord бота
echo ========================================

REM Проверка Java
echo Проверяем установку Java...
java -version >nul 2>&1
if errorlevel 1 (
    echo ❌ Java не установлена!
    echo Установите Java 17+ с официального сайта:
    echo https://adoptium.net/
    pause
    exit /b 1
) else (
    echo ✅ Java установлена
)

REM Создаем папку для Lavalink
if not exist "lavalink" mkdir lavalink
cd lavalink

REM Скачиваем Lavalink
echo Скачиваем Lavalink...
curl -L -o Lavalink.jar https://github.com/lavalink-devs/Lavalink/releases/latest/download/Lavalink.jar

if errorlevel 1 (
    echo Используем wget...
    wget -O Lavalink.jar https://github.com/lavalink-devs/Lavalink/releases/latest/download/Lavalink.jar
)

if not exist "Lavalink.jar" (
    echo ❌ Не удалось скачать Lavalink
    echo Скачайте вручную с: https://github.com/lavalink-devs/Lavalink/releases
    pause
    exit /b 1
)

echo ✅ Lavalink скачан

REM Создаем конфигурационный файл
echo Создаем конфигурационный файл...
(
echo server:
echo   port: 2333
echo   address: 127.0.0.1
echo lavalink:
echo   server:
echo     password: "youshallnotpass"
echo     sources:
echo       youtube: true
echo       bandcamp: true
echo       soundcloud: true
echo       twitch: true
echo       vimeo: true
echo       http: true
echo       local: false
echo metrics:
echo   prometheus:
echo     enabled: false
echo     endpoint: /metrics
echo sentry:
echo   dsn: ""
echo   environment: ""
echo logging:
echo   file:
echo     max-history: 30
echo     max-size: 1GB
echo   path: ./logs/
echo   level:
echo     root: INFO
echo     lavalink: INFO
) > application.yml

echo ✅ Конфигурация создана

echo.
echo 📋 Инструкция по запуску:
echo 1. Перейдите в папку lavalink: cd lavalink
echo 2. Запустите Lavalink: java -jar Lavalink.jar
echo 3. Оставьте Lavalink работать в отдельном окне
echo 4. Запустите бота в другом окне: python main.py
echo.
echo ⚠️ Примечание: Бот автоматически подключится к Lavalink
pause