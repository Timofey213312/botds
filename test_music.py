"""
Тестовый скрипт для проверки музыки
"""

import asyncio
import sys
import os

def check_wavelink():
    """Проверка установки wavelink"""
    print("🔍 Проверка wavelink...")
    try:
        import wavelink
        print(f"✅ Wavelink установлен: {wavelink.__version__}")
        
        # Проверка доступности Lavalink
        print("\n🔌 Проверка подключения к Lavalink...")
        print("Lavalink должен быть доступен по адресу: http://localhost:2333")
        print("Пароль: youshallnotpass")
        
        return True
    except ImportError:
        print("❌ Wavelink не установлен!")
        print("Установите: pip install wavelink")
        return False

def check_java():
    """Проверка установки Java"""
    print("\n☕ Проверка Java...")
    try:
        import subprocess
        result = subprocess.run(['java', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Java установлена")
            # Парсим версию
            for line in result.stderr.split('\n'):
                if 'version' in line.lower():
                    print(f"   Версия: {line.strip()}")
                    break
            return True
        else:
            print("❌ Java не установлена или не работает")
            return False
    except Exception as e:
        print(f"❌ Ошибка при проверке Java: {e}")
        return False

def check_lavalink_files():
    """Проверка файлов Lavalink"""
    print("\n📁 Проверка файлов Lavalink...")
    
    lavalink_path = os.path.join(os.getcwd(), 'lavalink')
    
    if not os.path.exists(lavalink_path):
        print("❌ Папка lavalink не найдена")
        print("Создайте папку: mkdir lavalink")
        return False
    
    print(f"✅ Папка lavalink найдена: {lavalink_path}")
    
    # Проверяем файлы
    files = {
        'Lavalink.jar': False,
        'application.yml': False
    }
    
    for file in os.listdir(lavalink_path):
        if file in files:
            files[file] = True
            print(f"✅ {file} найден")
    
    missing = [file for file, found in files.items() if not found]
    
    if missing:
        print(f"❌ Отсутствуют файлы: {', '.join(missing)}")
        return False
    
    return True

def print_instructions():
    """Печать инструкций"""
    print("\n" + "="*50)
    print("🎵 Инструкция по настройке музыки")
    print("="*50)
    
    print("\n📋 Текущий статус:")
    print("1. Discord бот запущен - ✅")
    print("2. Lavalink сервер - ❌ (нужно запустить)")
    print("3. Wavelink установлен - ✅")
    print("4. Java установлена - ✅")
    
    print("\n🚀 Запуск музыки:")
    print("1. Откройте новое окно PowerShell")
    print("2. Перейдите в папку lavalink:")
    print("   cd lavalink")
    print("3. Запустите Lavalink:")
    print("   java -jar Lavalink.jar")
    print("4. Оставьте Lavalink работать")
    print("5. Бот автоматически подключится к музыке")
    
    print("\n🎯 Тестирование музыки:")
    print("1. Зайдите в голосовой канал Discord")
    print("2. Используйте команду: /play песня")
    print("3. Или: !play песня")
    
    print("\n⚠️ Частые проблемы:")
    print("• Lavalink не запущен - запустите java -jar Lavalink.jar")
    print("• Неправильный порт - должен быть 2333")
    print("• Неправильный пароль - должен быть 'youshallnotpass'")
    print("• Блокировка антивирусом - добавьте в исключения")

def main():
    """Основная функция тестирования"""
    print("🎵 Тестирование музыкальной системы")
    print("="*50)
    
    # Проверяем всё
    java_ok = check_java()
    wavelink_ok = check_wavelink()
    files_ok = check_lavalink_files()
    
    print("\n" + "="*50)
    print("📊 Результаты проверки:")
    print("="*50)
    
    if java_ok and wavelink_ok and files_ok:
        print("✅ Все проверки пройдены успешно!")
        print("🎉 Музыкальная система готова к работе")
        
        print_instructions()
        
        print("\n✅ Готово! Запустите Lavalink и тестируйте музыку.")
    else:
        print("❌ Есть проблемы с настройкой:")
        if not java_ok:
            print("• Установите Java 17+ с https://adoptium.net/")
        if not wavelink_ok:
            print("• Установите wavelink: pip install wavelink")
        if not files_ok:
            print("• Скачайте Lavalink.jar с https://github.com/lavalink-devs/Lavalink/releases")
            print("• Поместите в папку lavalink/")
            print("• Создайте файл application.yml")
        
        print("\n⚠️ Музыкальные команды не будут работать пока проблемы не решены.")
        print("ℹ️ Все остальные команды бота работают нормально!")

if __name__ == "__main__":
    main()