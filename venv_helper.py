#!/usr/bin/env python3
"""
Venv Helper - Помощник для управления виртуальным окружением
Упрощает создание, активацию и управление виртуальным окружением (venv)
"""

import os
import sys
import subprocess
import platform
from pathlib import Path


class VenvHelper:
    """Класс для управления виртуальным окружением"""
    
    def __init__(self, venv_name: str = "venv"):
        """
        Инициализация помощника venv
        
        Args:
            venv_name: Имя папки виртуального окружения (по умолчанию 'venv')
        """
        self.venv_name = venv_name
        self.venv_path = Path(venv_name)
        self.is_windows = platform.system() == "Windows"
        self.python_cmd = "python" if self.is_windows else "python3"
        
    def venv_exists(self) -> bool:
        """Проверяет, существует ли виртуальное окружение"""
        return self.venv_path.exists() and (
            (self.venv_path / "bin" / "python").exists() or
            (self.venv_path / "Scripts" / "python.exe").exists()
        )
    
    def create(self) -> bool:
        """
        Создает виртуальное окружение
        
        Returns:
            True если успешно, False если ошибка
        """
        if self.venv_exists():
            print(f"✅ Виртуальное окружение '{self.venv_name}' уже существует")
            return True
        
        try:
            print(f"📦 Создание виртуального окружения '{self.venv_name}'...")
            subprocess.run(
                [self.python_cmd, "-m", "venv", self.venv_name],
                check=True,
                capture_output=False
            )
            print(f"✅ Виртуальное окружение успешно создано!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка при создании виртуального окружения: {e}")
            return False
    
    def get_activate_command(self) -> str:
        """Возвращает команду для активации виртуального окружения"""
        if self.is_windows:
            return f"{self.venv_name}\\Scripts\\activate"
        else:
            return f"source {self.venv_name}/bin/activate"
    
    def get_pip_path(self) -> Path:
        """Возвращает путь к pip в виртуальном окружении"""
        if self.is_windows:
            return self.venv_path / "Scripts" / "pip.exe"
        else:
            return self.venv_path / "bin" / "pip"
    
    def get_python_path(self) -> Path:
        """Возвращает путь к python в виртуальном окружении"""
        if self.is_windows:
            return self.venv_path / "Scripts" / "python.exe"
        else:
            return self.venv_path / "bin" / "python"
    
    def install_requirements(self, requirements_file: str = "requirements.txt") -> bool:
        """
        Устанавливает зависимости из файла requirements.txt
        
        Args:
            requirements_file: Путь к файлу requirements.txt
            
        Returns:
            True если успешно, False если ошибка
        """
        if not self.venv_exists():
            print(f"❌ Виртуальное окружение '{self.venv_name}' не найдено")
            print(f"   Сначала создайте его: python venv_helper.py create")
            return False
        
        req_path = Path(requirements_file)
        if not req_path.exists():
            print(f"❌ Файл '{requirements_file}' не найден")
            return False
        
        try:
            pip_path = self.get_pip_path()
            print(f"📥 Установка зависимостей из '{requirements_file}'...")
            subprocess.run(
                [str(pip_path), "install", "-r", requirements_file],
                check=True
            )
            print(f"✅ Зависимости успешно установлены!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка при установке зависимостей: {e}")
            return False
    
    def upgrade_pip(self) -> bool:
        """
        Обновляет pip, setuptools и wheel
        
        Returns:
            True если успешно, False если ошибка
        """
        if not self.venv_exists():
            print(f"❌ Виртуальное окружение '{self.venv_name}' не найдено")
            return False
        
        try:
            pip_path = self.get_pip_path()
            print("🔄 Обновление pip, setuptools и wheel...")
            subprocess.run(
                [str(pip_path), "install", "--upgrade", "pip", "setuptools", "wheel"],
                check=True
            )
            print("✅ pip успешно обновлен!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка при обновлении pip: {e}")
            return False
    
    def install_package(self, package: str) -> bool:
        """
        Устанавливает отдельный пакет
        
        Args:
            package: Имя пакета для установки
            
        Returns:
            True если успешно, False если ошибка
        """
        if not self.venv_exists():
            print(f"❌ Виртуальное окружение '{self.venv_name}' не найдено")
            return False
        
        try:
            pip_path = self.get_pip_path()
            print(f"📦 Установка пакета '{package}'...")
            subprocess.run(
                [str(pip_path), "install", package],
                check=True
            )
            print(f"✅ Пакет '{package}' успешно установлен!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка при установке пакета: {e}")
            return False
    
    def freeze_requirements(self, output_file: str = "requirements.txt") -> bool:
        """
        Сохраняет список установленных пакетов в файл
        
        Args:
            output_file: Путь к выходному файлу
            
        Returns:
            True если успешно, False если ошибка
        """
        if not self.venv_exists():
            print(f"❌ Виртуальное окружение '{self.venv_name}' не найдено")
            return False
        
        try:
            pip_path = self.get_pip_path()
            print(f"💾 Сохранение зависимостей в '{output_file}'...")
            with open(output_file, 'w') as f:
                subprocess.run(
                    [str(pip_path), "freeze"],
                    stdout=f,
                    check=True
                )
            print(f"✅ Зависимости успешно сохранены в '{output_file}'!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка при сохранении зависимостей: {e}")
            return False
    
    def list_packages(self) -> bool:
        """
        Выводит список установленных пакетов
        
        Returns:
            True если успешно, False если ошибка
        """
        if not self.venv_exists():
            print(f"❌ Виртуальное окружение '{self.venv_name}' не найдено")
            return False
        
        try:
            pip_path = self.get_pip_path()
            print("📋 Установленные пакеты:")
            print("-" * 50)
            subprocess.run([str(pip_path), "list"], check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка при выводе списка пакетов: {e}")
            return False
    
    def remove(self) -> bool:
        """
        Удаляет виртуальное окружение
        
        Returns:
            True если успешно, False если ошибка
        """
        if not self.venv_exists():
            print(f"⚠️  Виртуальное окружение '{self.venv_name}' не найдено")
            return False
        
        try:
            import shutil
            print(f"🗑️  Удаление виртуального окружения '{self.venv_name}'...")
            shutil.rmtree(self.venv_path)
            print(f"✅ Виртуальное окружение успешно удалено!")
            return True
        except Exception as e:
            print(f"❌ Ошибка при удалении виртуального окружения: {e}")
            return False
    
    def status(self) -> None:
        """Выводит информацию о статусе виртуального окружения"""
        print(f"\n{'='*60}")
        print(f"📊 Информация о виртуальном окружении")
        print(f"{'='*60}")
        print(f"Имя: {self.venv_name}")
        print(f"Путь: {self.venv_path.absolute()}")
        print(f"ОС: {'Windows' if self.is_windows else 'Linux/MacOS'}")
        print(f"Статус: {'✅ Существует' if self.venv_exists() else '❌ Не найдено'}")
        print(f"Python: {self.get_python_path()}")
        print(f"Pip: {self.get_pip_path()}")
        print(f"Активация: {self.get_activate_command()}")
        print(f"{'='*60}\n")


def print_help():
    """Выводит справку по использованию"""
    help_text = """
╔═══════════════════════════════════════════════════════════╗
║           VEnv Helper - Помощник для виртуального окружения║
╚═══════════════════════════════════════════════════════════╝

📖 ИСПОЛЬЗОВАНИЕ:
    python venv_helper.py <команда> [опции]

🔧 ДОСТУПНЫЕ КОМАНДЫ:

    create              Создать виртуальное окружение
    install-req         Установить зависимости из requirements.txt
    install <пакет>     Установить отдельный пакет
    upgrade-pip         Обновить pip, setuptools и wheel
    freeze              Сохранить список зависимостей
    list                Вывести список установленных пакетов
    remove              Удалить виртуальное окружение
    status              Информация о статусе
    help                Эта справка

📝 ПРИМЕРЫ:

    # Полная установка
    python venv_helper.py create
    python venv_helper.py install-req
    
    # Установить конкретный пакет
    python venv_helper.py install requests
    
    # Обновить pip
    python venv_helper.py upgrade-pip
    
    # Сохранить зависимости
    python venv_helper.py freeze
    
    # Удалить окружение
    python venv_helper.py remove

🎯 БЫСТРЫЙ СТАРТ:
    
    1. python venv_helper.py create
    2. source venv/bin/activate  (или venv\\Scripts\\activate на Windows)
    3. python venv_helper.py install-req
    4. python bot.py
    """
    print(help_text)


def main():
    """Основная функция"""
    if len(sys.argv) < 2:
        print_help()
        return
    
    command = sys.argv[1]
    helper = VenvHelper()
    
    if command == "create":
        helper.create()
        print(f"\n💡 Активируйте окружение:")
        print(f"   {helper.get_activate_command()}")
    
    elif command == "install-req":
        if helper.create():
            helper.install_requirements()
    
    elif command == "install" and len(sys.argv) > 2:
        package = sys.argv[2]
        helper.install_package(package)
    
    elif command == "upgrade-pip":
        helper.upgrade_pip()
    
    elif command == "freeze":
        helper.freeze_requirements()
    
    elif command == "list":
        helper.list_packages()
    
    elif command == "remove":
        confirm = input(f"⚠️  Вы уверены? (y/n): ").lower()
        if confirm == 'y':
            helper.remove()
    
    elif command == "status":
        helper.status()
    
    elif command in ["help", "-h", "--help"]:
        print_help()
    
    else:
        print(f"❌ Неизвестная команда: {command}")
        print("   Введите 'python venv_helper.py help' для справки")


if __name__ == "__main__":
    main()
