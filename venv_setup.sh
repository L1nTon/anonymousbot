#!/bin/bash

# VEnv Helper - Bash скрипт для управления виртуальным окружением
# Упрощает работу с venv на Linux/MacOS

set -e

VENV_DIR="venv"
PYTHON_CMD="python3"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для вывода помощи
print_help() {
    cat << 'HELP'

╔═══════════════════════════════════════════════════════════╗
║     VEnv Helper - Помощник для виртуального окружения      ║
║                    Bash версия                             ║
╚═══════════════════════════════════════════════════════════╝

�� ИСПОЛЬЗОВАНИЕ:
    ./venv_setup.sh <команда>

🔧 ДОСТУПНЫЕ КОМАНДЫ:

    create              Создать виртуальное окружение
    activate            Активировать окружение (инструкция)
    install             Установить зависимости из requirements.txt
    install-pkg <имя>   Установить отдельный пакет
    upgrade             Обновить pip, setuptools и wheel
    freeze              Сохранить список зависимостей
    list                Вывести список пакетов
    clean               Удалить виртуальное окружение
    status              Информация о статусе
    help                Эта справка

📝 ПРИМЕРЫ:

    # Полная установка
    ./venv_setup.sh create
    source venv/bin/activate
    ./venv_setup.sh install
    
    # Установить конкретный пакет
    ./venv_setup.sh install-pkg requests
    
    # Очистить окружение
    ./venv_setup.sh clean

HELP
}

# Функция для проверки существования venv
venv_exists() {
    [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/python" ]
}

# Функция для создания venv
create_venv() {
    if venv_exists; then
        echo -e "${GREEN}✅ Виртуальное окружение '$VENV_DIR' уже существует${NC}"
        return 0
    fi
    
    echo -e "${BLUE}📦 Создание виртуального окружения '$VENV_DIR'...${NC}"
    $PYTHON_CMD -m venv "$VENV_DIR"
    echo -e "${GREEN}✅ Виртуальное окружение успешно создано!${NC}"
    echo -e "${YELLOW}💡 Активируйте окружение:${NC}"
    echo -e "${BLUE}   source $VENV_DIR/bin/activate${NC}"
}

# Функция для установки зависимостей
install_requirements() {
    if ! venv_exists; then
        echo -e "${RED}❌ Виртуальное окружение не найдено${NC}"
        echo -e "${YELLOW}   Сначала создайте его: ./venv_setup.sh create${NC}"
        return 1
    fi
    
    if [ ! -f "requirements.txt" ]; then
        echo -e "${RED}❌ Файл 'requirements.txt' не найден${NC}"
        return 1
    fi
    
    echo -e "${BLUE}📥 Установка зависимостей...${NC}"
    "$VENV_DIR/bin/pip" install -r requirements.txt
    echo -e "${GREEN}✅ Зависимости успешно установлены!${NC}"
}

# Функция для установки отдельного пакета
install_package() {
    local package=$1
    
    if [ -z "$package" ]; then
        echo -e "${RED}❌ Укажите имя пакета${NC}"
        return 1
    fi
    
    if ! venv_exists; then
        echo -e "${RED}❌ Виртуальное окружение не найдено${NC}"
        return 1
    fi
    
    echo -e "${BLUE}📦 Установка пакета '$package'...${NC}"
    "$VENV_DIR/bin/pip" install "$package"
    echo -e "${GREEN}✅ Пакет успешно установлен!${NC}"
}

# Функция для обновления pip
upgrade_pip() {
    if ! venv_exists; then
        echo -e "${RED}❌ Виртуальное окружение не найдено${NC}"
        return 1
    fi
    
    echo -e "${BLUE}🔄 Обновление pip, setuptools и wheel...${NC}"
    "$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel
    echo -e "${GREEN}✅ pip успешно обновлен!${NC}"
}

# Функция для сохранения зависимостей
freeze_requirements() {
    if ! venv_exists; then
        echo -e "${RED}❌ Виртуальное окружение не найдено${NC}"
        return 1
    fi
    
    echo -e "${BLUE}💾 Сохранение зависимостей...${NC}"
    "$VENV_DIR/bin/pip" freeze > requirements.txt
    echo -e "${GREEN}✅ Зависимости сохранены в requirements.txt${NC}"
}

# Функция для вывода списка пакетов
list_packages() {
    if ! venv_exists; then
        echo -e "${RED}❌ Виртуальное окружение не найдено${NC}"
        return 1
    fi
    
    echo -e "${BLUE}📋 Установленные пакеты:${NC}"
    echo "---"
    "$VENV_DIR/bin/pip" list
}

# Функция для удаления venv
remove_venv() {
    if ! venv_exists; then
        echo -e "${YELLOW}⚠️  Виртуальное окружение не найдено${NC}"
        return 0
    fi
    
    read -p "⚠️  Вы уверены? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}🗑️  Удаление виртуального окружения...${NC}"
        rm -rf "$VENV_DIR"
        echo -e "${GREEN}✅ Виртуальное окружение удалено!${NC}"
    else
        echo -e "${YELLOW}❌ Отменено${NC}"
    fi
}

# Функция для вывода статуса
show_status() {
    echo -e "\n${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}📊 Информация о виртуальном окружении${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo "Имя: $VENV_DIR"
    echo "Путь: $(pwd)/$VENV_DIR"
    echo "ОС: $(uname -s)"
    
    if venv_exists; then
        echo -e "Статус: ${GREEN}✅ Существует${NC}"
        echo "Python: $($VENV_DIR/bin/python --version)"
        echo "Pip: $($VENV_DIR/bin/pip --version)"
    else
        echo -e "Статус: ${RED}❌ Не найдено${NC}"
    fi
    
    echo "Активация: source $VENV_DIR/bin/activate"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}\n"
}

# Функция для активации окружения
show_activate_help() {
    echo -e "\n${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║           Активация виртуального окружения                ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}\n"
    echo -e "${YELLOW}Для активации окружения в текущей оболочке выполните:${NC}"
    echo -e "\n${GREEN}source venv/bin/activate${NC}\n"
    echo -e "${YELLOW}После этого вы сможете:${NC}"
    echo "  • Использовать python и pip из окружения"
    echo "  • Запускать скрипты из проекта"
    echo "  • Устанавливать локальные зависимости\n"
    echo -e "${YELLOW}Для выхода из окружения выполните:${NC}"
    echo -e "\n${GREEN}deactivate${NC}\n"
}

# Основная логика
case "${1:-help}" in
    create)
        create_venv
        ;;
    activate)
        show_activate_help
        ;;
    install)
        install_requirements
        ;;
    install-pkg)
        install_package "$2"
        ;;
    upgrade)
        upgrade_pip
        ;;
    freeze)
        freeze_requirements
        ;;
    list)
        list_packages
        ;;
    clean)
        remove_venv
        ;;
    status)
        show_status
        ;;
    help|-h|--help)
        print_help
        ;;
    *)
        echo -e "${RED}❌ Неизвестная команда: $1${NC}"
        echo "Введите './venv_setup.sh help' для справки"
        exit 1
        ;;
esac
