"""
Тестовый скрипт для проверки бота
"""

import asyncio
import sys
import os

def check_dependencies():
    """Проверка зависимостей"""
    print("🔍 Проверка зависимостей...")
    
    required = [
        ('discord.py', 'discord'),
        ('python-dotenv', 'dotenv'),
        ('aiosqlite', 'aiosqlite'),
        ('aiohttp', 'aiohttp'),
        ('wavelink', 'wavelink'),
        ('yt-dlp', 'yt_dlp')
    ]
    
    missing = []
    
    for package_name, import_name in required:
        try:
            __import__(import_name)
            print(f"✅ {package_name}")
        except ImportError:
            missing.append(package_name)
            print(f"❌ {package_name}")
    
    if missing:
        print(f"\n⚠️ Отсутствуют зависимости: {', '.join(missing)}")
        print("Установите их командой: pip install -r requirements.txt")
        return False
    
    print("✅ Все зависимости установлены")
    return True

def check_config():
    """Проверка конфигурации"""
    print("\n🔧 Проверка конфигурации...")
    
    if not os.path.exists('.env'):
        print("❌ Файл .env не найден")
        print("Создайте файл .env на основе .env.example")
        return False
    
    with open('.env', 'r', encoding='utf-8') as f:
        content = f.read()
        
        if 'YOUR_BOT_TOKEN_HERE' in content:
            print("❌ Токен бота не настроен")
            print("Замените YOUR_BOT_TOKEN_HERE на ваш токен в файле .env")
            return False
    
    print("✅ Конфигурация проверена")
    return True

def check_structure():
    """Проверка структуры проекта"""
    print("\n📁 Проверка структуры проекта...")
    
    required_files = [
        'main.py',
        'requirements.txt',
        '.env',
        'modules/__init__.py',
        'modules/moderation.py',
        'modules/music.py',
        'modules/economy.py',
        'modules/games.py',
        'modules/utilities.py',
        'modules/help.py'
    ]
    
    missing = []
    
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            missing.append(file)
            print(f"❌ {file}")
    
    if missing:
        print(f"\n⚠️ Отсутствуют файлы: {', '.join(missing)}")
        return False
    
    print("✅ Структура проекта проверена")
    return True

def print_instructions():
    """Печать инструкций"""
    print("\n" + "="*50)
    print("🎉 Бот готов к запуску!")
    print("="*50)
    
    print("\n📋 Инструкции по запуску:")
    print("1. Убедитесь что у вас установлен Python 3.8+")
    print("2. Установите зависимости: pip install -r requirements.txt")
    print("3. Настройте токен бота в файле .env")
    print("4. Для музыки запустите Lavalink сервер (опционально)")
    print("5. Запустите бота: python main.py")
    
    print("\n⚙️ Основные команды:")
    print("• !help - Показать все команды")
    print("• !ping - Проверить пинг бота")
    print("• !stats - Статистика бота")
    
    print("\n⚠️ Примечания:")
    print("• Для модерационных команд нужны соответствующие права")
    print("• Музыка требует запущенного Lavalink сервера")
    print("• Экономическая система сохраняет данные в SQLite БД")

def main():
    """Основная функция тестирования"""
    print("🤖 Тестирование Discord бота")
    print("="*50)
    
    # Проверяем зависимости
    if not check_dependencies():
        sys.exit(1)
    
    # Проверяем конфигурацию
    if not check_config():
        sys.exit(1)
    
    # Проверяем структуру
    if not check_structure():
        sys.exit(1)
    
    # Печатаем инструкции
    print_instructions()
    
    print("\n✅ Тестирование завершено успешно!")
    print("\nЗапустите бота командой: python main.py")

if __name__ == "__main__":
    main()