"""
Проверка Lavalink подключения
"""

import requests
import socket
import subprocess
import time
import os

print("🔍 Проверка Lavalink")
print("="*50)

def check_port(port=2333):
    """Проверка доступности порта"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        return result == 0
    except:
        return False

def check_lavalink_http():
    """Проверка HTTP ответа Lavalink"""
    try:
        response = requests.get("http://localhost:2333", timeout=3)
        return response.status_code == 404  # Lavalink возвращает 404 на корневой запрос
    except requests.exceptions.ConnectionError:
        return False
    except:
        return None

def check_java():
    """Проверка установки Java"""
    try:
        result = subprocess.run(['java', '-version'], capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

def check_lavalink_files():
    """Проверка файлов Lavalink"""
    files_to_check = ['Lavalink.jar', 'application.yml']
    missing = []
    
    for file in files_to_check:
        if not os.path.exists(f'lavalink/{file}'):
            missing.append(file)
    
    return missing

print("\n📋 Проверка компонентов:")
print("-" * 30)

# Проверяем Java
java_ok = check_java()
print(f"☕ Java: {'✅ Установлена' if java_ok else '❌ Не установлена'}")

# Проверяем порт
port_ok = check_port(2333)
print(f"🔌 Порт 2333: {'✅ Открыт' if port_ok else '❌ Закрыт'}")

# Проверяем HTTP
http_status = check_lavalink_http()
if http_status is True:
    print(f"🌐 HTTP: ✅ Lavalink работает")
elif http_status is False:
    print(f"🌐 HTTP: ❌ Lavalink не отвечает")
else:
    print(f"🌐 HTTP: ⚠️ Ошибка проверки")

# Проверяем файлы
missing_files = check_lavalink_files()
if missing_files:
    print(f"📁 Файлы: ❌ Отсутствуют: {', '.join(missing_files)}")
else:
    print(f"📁 Файлы: ✅ Все файлы на месте")

print("\n" + "="*50)

if port_ok and http_status:
    print("🎉 Lavalink работает правильно!")
    print("\n📊 Статус: ✅ ГОТОВ К РАБОТЕ")
    
elif not java_ok:
    print("❌ Java не установлена!")
    print("\n📋 Решение:")
    print("1. Скачайте Java 17+ с https://adoptium.net/")
    print("2. Установите как обычную программу")
    print("3. Проверьте: java -version")
    
elif missing_files:
    print("❌ Отсутствуют файлы Lavalink!")
    print("\n📋 Решение:")
    print("1. Скачайте Lavalink.jar с https://github.com/lavalink-devs/Lavalink/releases")
    print("2. Поместите в папку lavalink/")
    print("3. Убедитесь что application.yml правильный")
    
elif not port_ok:
    print("❌ Lavalink не запущен!")
    print("\n📋 Решение:")
    print("1. Откройте новое окно PowerShell")
    print("2. Перейдите в папку lavalink: cd lavalink")
    print("3. Запустите: java -jar Lavalink.jar")
    print("4. Оставьте окно открытым")
    
else:
    print("⚠️ Неизвестная проблема с Lavalink")
    print("\n📋 Диагностика:")
    print("1. Проверьте файл application.yml")
    print("2. Проверьте что нет блокировки антивирусом")
    print("3. Попробуйте перезапустить Lavalink")

print("\n" + "="*50)
print("🚀 Быстрая проверка командой:")
print("curl -I http://localhost:2333")
print("\n📝 Если Lavalink работает, должно быть:")
print("HTTP/1.1 404 Not Found")

print("\n🎵 Если проблемы остаются:")
print("1. Бот будет работать БЕЗ музыки")
print("2. Все другие 60+ команд работают")
print("3. Музыку можно настроить позже")