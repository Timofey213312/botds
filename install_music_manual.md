# Установка Lavalink для музыки (опционально)

Музыкальные команды в боте требуют Lavalink сервер. Это опционально - бот будет работать и без музыки.

## 📥 Скачать Lavalink вручную:

1. **Перейдите на страницу релизов:**
   https://github.com/lavalink-devs/Lavalink/releases

2. **Скачайте последнюю версию:**
   - Ищите файл `Lavalink.jar`
   - Например: `Lavalink.4.0.0.jar`

3. **Создайте папку `lavalink` в директории бота:**
   ```bash
   mkdir lavalink
   cd lavalink
   ```

4. **Поместите `Lavalink.jar` в папку `lavalink`**

5. **Создайте файл `application.yml`:**

Создайте файл `lavalink/application.yml` с содержимым:

```yaml
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
```

## ▶️ Запуск Lavalink:

1. **Откройте командную строку в папке `lavalink`:**
   ```bash
   cd lavalink
   ```

2. **Запустите Lavalink:**
   ```bash
   java -jar Lavalink.jar
   ```

3. **Оставьте Lavalink работать в отдельном окне**

4. **Запустите бота в другом окне:**
   ```bash
   python main_fixed.py
   ```

## ⚠️ Требования:

- **Java 17+** - установите с https://adoptium.net/
- **Стабильное интернет-соединение**

## 🎵 Что будет работать без Lavalink:

✅ Все команды КРОМЕ музыкальных:
- Модерация (`!kick`, `!ban`, `!clear`)
- Экономика (`!balance`, `!daily`, `!shop`)
- Игры (`!rps`, `!slot`, `!8ball`)
- Утилиты (`!serverinfo`, `!ping`, `!weather`)

## ❌ Что НЕ будет работать без Lavalink:

- `!play` - воспроизведение музыки
- `!pause` / `!resume` - управление музыкой
- `!queue` - очередь треков
- `!volume` - громкость
- `!skip` / `!stop` - пропуск/остановка
- `!loop` / `!shuffle` - режимы повтора
- `!nowplaying` - текущий трек
- `!leave` - выход из канала

## 🔧 Установка Java:

1. **Скачайте Java 17+** с https://adoptium.net/
2. **Установите** как обычную программу
3. **Проверьте установку:**
   ```bash
   java -version
   ```
   Должно показать версию Java 17 или выше

## 💡 Советы:

1. **Бот запустится быстрее без попыток подключения к Lavalink**
2. **Вы всегда можете установить музыку позже**
3. **Большинство функций бота не требуют Lavalink**
4. **Вы можете запускать Lavalink только когда нужна музыка**

## 🚀 Быстрый старт без музыки:

Просто запустите бота без установки Lavalink:
```bash
python main_fixed.py
```

Бот будет работать со всеми функциями кроме музыки!