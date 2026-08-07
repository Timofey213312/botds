FROM python:3.11-slim

# Устанавливаем ffmpeg (нужен для музыки) и зависимости сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# yt-dlp регулярно ломается YouTube — ставим всегда свежую версию
RUN pip install --no-cache-dir -U yt-dlp

# Копируем код
COPY . .

# Порт (не используется для бота, но Railway ждёт порт)
ENV PORT=8080
EXPOSE 8080

# Запуск бота
CMD ["python", "main.py"]
