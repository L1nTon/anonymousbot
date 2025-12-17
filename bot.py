#!/usr/bin/env python3
"""
Anonymous Bot - Telegram бот для анонимных сообщений
Версия 2.0 с SQLite базой данных
"""

import os
import logging
import uuid
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, CallbackQueryHandler, filters
)
from database import Database

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальная переменная для хранения application (нужна для отправки логов)
_bot_application = None


class TelegramLogHandler(logging.Handler):
    """Кастомный обработчик логов, который отправляет WARNING и ERROR в Telegram"""

    def __init__(self, admin_id: int):
        super().__init__()
        self.admin_id = admin_id
        self.setLevel(logging.WARNING)  # Отправляем только WARNING и ERROR

    def emit(self, record):
        """Отправляет лог-сообщение в Telegram"""
        global _bot_application

        if _bot_application is None:
            return

        try:
            log_entry = self.format(record)
            error_type = "⚠️ WARNING" if record.levelno == logging.WARNING else "🔴 ERROR"

            # Ограничиваем длину
            if len(log_entry) > 3800:
                log_entry = log_entry[:3800] + "\n... (обрезано)"

            message = f"{error_type}\n\n<code>{log_entry}</code>"

            # Отправляем асинхронно
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Если цикл уже запущен, создаем задачу
                    asyncio.create_task(
                        _bot_application.bot.send_message(
                            chat_id=self.admin_id,
                            text=message,
                            parse_mode='HTML'
                        )
                    )
                else:
                    # Если цикла нет, запускаем синхронно
                    loop.run_until_complete(
                        _bot_application.bot.send_message(
                            chat_id=self.admin_id,
                            text=message,
                            parse_mode='HTML'
                        )
                    )
            except Exception:
                # Если не получилось отправить, просто игнорируем
                pass

        except Exception:
            # Не логируем ошибки в самом обработчике логов, чтобы избежать рекурсии
            pass

# Состояния для ConversationHandler
WAITING_FOR_MESSAGE = 1
WAITING_FOR_REPLY = 2

# Глобальные переменные
user_message = {}
admin_awaiting_reply = {}  # {admin_id: message_id}

# Инициализация базы данных
db = Database()
logger.info("✅ База данных SQLite инициализирована")

# ID администратора для отправки ошибок
ERROR_REPORT_ADMIN_ID = 1873601165


async def send_error_to_admin(context: ContextTypes.DEFAULT_TYPE, error_message: str, error_type: str = "ERROR") -> None:
    """Отправляет сообщение об ошибке администратору"""
    try:
        emoji = "🔴" if error_type == "ERROR" else "⚠️"
        message = f"{emoji} <b>{error_type}</b>\n\n<code>{error_message}</code>"

        await context.bot.send_message(
            chat_id=ERROR_REPORT_ADMIN_ID,
            text=message,
            parse_mode='HTML'
        )
        logger.info(f"✅ {error_type} отправлен администратору {ERROR_REPORT_ADMIN_ID}")
    except Exception as e:
        logger.error(f"❌ Не удалось отправить {error_type} администратору: {e}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик всех ошибок в боте"""
    import traceback

    # Получаем полную информацию об ошибке
    error = context.error
    tb_string = ''.join(traceback.format_exception(None, error, error.__traceback__))

    # Формируем сообщение об ошибке
    error_message = f"Exception: {error}\n\n{tb_string}"

    # Ограничиваем длину сообщения (Telegram лимит 4096 символов)
    if len(error_message) > 3800:
        error_message = error_message[:3800] + "\n\n... (сообщение обрезано)"

    # Логируем ошибку
    logger.error(f"🔴 Ошибка в боте: {error}")
    logger.error(tb_string)

    # Отправляем администратору
    await send_error_to_admin(context, error_message, "ERROR")

    # Если есть update, пытаемся уведомить пользователя
    if update and isinstance(update, Update):
        if update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ Произошла ошибка. Администратор уведомлен."
                )
            except Exception:
                pass


def get_recipients():
    """Получает список ID получателей из переменной окружения"""
    recipients_str = os.getenv('RECIPIENTS', os.getenv('ADMIN_ID', ''))
    if not recipients_str:
        logger.error("❌ Не указаны получатели сообщений (RECIPIENTS или ADMIN_ID)")
        return []

    recipients = []
    for recipient_id in recipients_str.split(','):
        recipient_id = recipient_id.strip()
        if recipient_id:
            try:
                recipients.append(int(recipient_id))
            except ValueError:
                logger.warning(f"⚠️ Некорректный ID получателя: {recipient_id}")

    logger.info(f"📋 Получатели сообщений: {recipients}")
    return recipients


def generate_message_id():
    """Генерирует уникальный ID для сообщения"""
    return str(uuid.uuid4())[:8]


async def send_to_all_recipients(context, text, reply_markup=None, parse_mode='HTML'):
    """Отправляет сообщение всем получателям (администраторам и группам)"""
    recipients = get_recipients()
    success_count = 0
    failed_recipients = []

    for recipient_id in recipients:
        try:
            await context.bot.send_message(
                chat_id=recipient_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            success_count += 1
            logger.info(f"✅ Сообщение отправлено получателю {recipient_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки получателю {recipient_id}: {e}")
            failed_recipients.append(recipient_id)

    return success_count, failed_recipients


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    user = update.effective_user
    user_id = user.id
    admin_id = int(os.getenv('ADMIN_ID'))

    # Сохраняем информацию о пользователе в базу данных
    db.add_or_update_user(
        user_id=user_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        full_name=user.full_name,
        is_bot=user.is_bot,
        is_premium=user.is_premium if hasattr(user, 'is_premium') else False,
        language_code=user.language_code
    )

    logger.info(f"👤 Пользователь {user_id} ({user.full_name}) использовал /start")

    # Проверяем, является ли пользователь одним из получателей
    recipients = get_recipients()
    is_recipient = user_id in recipients

    if is_recipient:
        welcome_text = """
👋 Добро пожаловать в Anonymous Bot!

Вы администратор бота. Доступные команды:

/help - Справка
/myid - Узнать ваш ID
/messages - Список сообщений

🌐 Веб-интерфейс: http://localhost:5000
        """
    else:
        welcome_text = """
👋 Добро пожаловать в Anonymous Bot!

Этот бот позволяет отправлять анонимные сообщения.

💬 Просто напишите любое сообщение, и оно будет отправлено!

✅ Ваши сообщения полностью анонимны
✅ Вы получите ответ прямо в этом чате

Используйте /help для получения дополнительной информации
        """

        # Уведомляем всех администраторов о новом пользователе
        user_info = format_user_info(user)
        notification_text = f"🆕 Новый пользователь запустил бота:\n\n{user_info}"

        try:
            success_count, failed = await send_to_all_recipients(
                context=context,
                text=notification_text,
                parse_mode='HTML'
            )
            logger.info(f"✅ Уведомление о новом пользователе {user_id} отправлено {success_count} получателям")
            if failed:
                logger.warning(f"⚠️ Не удалось отправить уведомление получателям: {failed}")
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке уведомления о новом пользователе: {e}")

    await update.message.reply_text(welcome_text)


def format_user_info(user) -> str:
    """Форматирует информацию о пользователе для отправки администратору"""
    user_info_parts = []

    # Имя пользователя с кликабельной ссылкой
    user_name = user.full_name or user.first_name or "Не указано"
    user_link = f'<a href="tg://user?id={user.id}">{user_name}</a>'
    user_info_parts.append(f"👤 От: {user_link}")

    # Username
    if user.username:
        user_info_parts.append(f"📱 Username: @{user.username}")
    else:
        user_info_parts.append("📱 Username: Не указан")

    # ID пользователя
    user_info_parts.append(f"🆔 ID: <code>{user.id}</code>")

    # Дополнительная информация
    if hasattr(user, 'is_premium') and user.is_premium:
        user_info_parts.append("⭐ Premium: Да")

    if user.language_code:
        user_info_parts.append(f"🌐 Язык: {user.language_code}")

    return "\n".join(user_info_parts)


async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало процесса отправки анонимного сообщения"""
    await update.message.reply_text(
        "📝 Напишите ваше сообщение (максимум 4096 символов):"
    )
    return WAITING_FOR_MESSAGE


async def receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получаем сообщение от пользователя и сразу отправляем"""
    message_text = update.message.text
    user = update.effective_user
    user_id = user.id

    if len(message_text) > 4096:
        await update.message.reply_text(
            "❌ Сообщение слишком длинное! Максимум 4096 символов."
        )
        return WAITING_FOR_MESSAGE

    admin_id = int(os.getenv('ADMIN_ID'))

    try:
        # Генерируем ID сообщения
        message_id = generate_message_id()

        # Обновляем информацию о пользователе
        db.add_or_update_user(
            user_id=user_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=user.full_name,
            is_bot=user.is_bot,
            is_premium=user.is_premium if hasattr(user, 'is_premium') else False,
            language_code=user.language_code
        )

        # Сохраняем сообщение в базу данных
        db.add_message(
            message_id=message_id,
            user_id=user_id,
            message_text=message_text,
            is_from_admin=False
        )

        # Формируем информацию о пользователе
        user_info = format_user_info(user)

        # Создаем кнопку для ответа
        keyboard = [
            [InlineKeyboardButton("💬 Ответить", callback_data=f"reply_{message_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Отправляем сообщение всем получателям
        message_text_formatted = f"📨 Новое сообщение:\n\n{user_info}\n\n📝 Текст:\n{message_text}\n\n🔑 Message ID: <code>{message_id}</code>"
        success_count, failed = await send_to_all_recipients(
            context=context,
            text=message_text_formatted,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

        logger.info(f"📨 Сообщение {message_id} отправлено {success_count} получателям")
        if failed:
            logger.warning(f"⚠️ Не удалось отправить получателям: {failed}")

        # Подтверждаем пользователю
        if success_count > 0:
            await update.message.reply_text(
                "✅ Сообщение успешно отправлено!"
            )
        else:
            await update.message.reply_text(
                "❌ Не удалось отправить сообщение. Попробуйте позже."
            )

    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
        await update.message.reply_text(
            "❌ Ошибка при отправке сообщения. Попробуйте позже."
        )

    return ConversationHandler.END


async def reply_button_pressed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Администратор нажимает кнопку 'Ответить'"""
    query = update.callback_query
    await query.answer()

    admin_id = query.from_user.id
    callback_data = query.data
    message_id = callback_data.replace("reply_", "")

    logger.info(f"🔘 Администратор {admin_id} нажал кнопку 'Ответить' для сообщения {message_id}")

    # Проверяем, что сообщение существует в базе данных
    message = db.get_message(message_id)
    if not message:
        await query.answer("❌ Сообщение не найдено в базе данных", show_alert=True)
        logger.warning(f"⚠️ Сообщение {message_id} не найдено в БД")
        return ConversationHandler.END

    # Сохраняем информацию о том, что администратор ждет ответа
    admin_awaiting_reply[admin_id] = message_id
    logger.info(f"✅ Администратор {admin_id} переведен в состояние WAITING_FOR_REPLY для сообщения {message_id}")

    # Отправляем новое сообщение с запросом ответа (не изменяем оригинальное)
    await context.bot.send_message(
        chat_id=admin_id,
        text=f"💬 Напишите ответ для пользователя (ID сообщения: {message_id}):\n\n"
             "Введите /cancel для отмены"
    )

    return WAITING_FOR_REPLY


async def receive_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получаем ответ администратора"""
    admin_id = update.effective_user.id

    logger.info(f"📝 Получен текст от администратора {admin_id} в состоянии WAITING_FOR_REPLY")

    if admin_id not in admin_awaiting_reply:
        logger.error(f"❌ Администратор {admin_id} не найден в admin_awaiting_reply")
        await update.message.reply_text("❌ Ошибка: сеанс ответа не найден")
        return ConversationHandler.END

    reply_text = update.message.text
    message_id = admin_awaiting_reply[admin_id]

    logger.info(f"📨 Администратор {admin_id} отправляет ответ на сообщение {message_id}: {reply_text[:50]}...")

    # Получаем сообщение из базы данных
    message = db.get_message(message_id)
    if not message:
        logger.error(f"❌ Сообщение {message_id} не найдено в БД")
        await update.message.reply_text("❌ Исходное сообщение не найдено")
        del admin_awaiting_reply[admin_id]
        return ConversationHandler.END

    try:
        user_id = message['user_id']

        # Отправляем ответ пользователю
        await context.bot.send_message(
            chat_id=user_id,
            text=f"💬 Ответ на ваше анонимное сообщение:\n\n{reply_text}"
        )

        # Сохраняем ответ администратора в базу данных
        db.add_admin_reply(
            message_id=message_id,
            admin_id=admin_id,
            reply_text=reply_text
        )

        # Подтверждаем администратору
        await update.message.reply_text("✅ Ответ отправлен пользователю!")

        # Удаляем из очереди ожидания
        del admin_awaiting_reply[admin_id]

    except Exception as e:
        logger.error(f"Ошибка при отправке ответа: {e}")
        await update.message.reply_text(
            f"❌ Ошибка при отправке ответа: {e}\nПопробуйте позже."
        )
        # Удаляем из очереди ожидания даже при ошибке
        if admin_id in admin_awaiting_reply:
            del admin_awaiting_reply[admin_id]

    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help"""
    user_id = update.effective_user.id
    admin_id = int(os.getenv('ADMIN_ID'))
    
    if user_id == admin_id:
        help_text = """
📚 Команды администратора:

/help - Справка
/myid - Узнать ваш ID
/messages - Список сообщений в базе

📋 Как отвечать на сообщения:
1. Дождитесь анонимного сообщения
2. Нажмите кнопку "💬 Ответить"
3. Напишите свой ответ
4. Ответ будет отправлен пользователю анонимно

🌐 Веб-интерфейс:
Откройте http://localhost:5000 для управления сообщениями
        """
    else:
        help_text = """
📚 Доступные команды:

/start - Начало работы
/help - Справка
/cancel - Отменить текущую операцию
/myid - Узнать ваш ID

ℹ️ Как пользоваться ботом:
Просто напишите любое сообщение боту, и оно будет анонимно отправлено!

✅ Ваши сообщения полностью анонимны
✅ Вы получите ответ прямо в этом чате
4. Ждите ответа
        """
    
    await update.message.reply_text(help_text)


async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /myid"""
    user_id = update.effective_user.id
    await update.message.reply_text(f"🔍 Ваш ID: `{user_id}`", parse_mode="Markdown")


async def messages_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /messages (только для администратора)"""
    user_id = update.effective_user.id
    admin_id = int(os.getenv('ADMIN_ID'))

    if user_id != admin_id:
        await update.message.reply_text("❌ Эта команда доступна только администратору")
        return

    # Получаем все сообщения из базы данных
    messages = db.get_all_messages()

    if not messages:
        await update.message.reply_text("📭 Нет сообщений в базе данных")
        return

    message_list = "📋 Сообщения в базе:\n\n"
    for msg in messages[:10]:  # Показываем только последние 10
        message_id = msg['message_id']
        user_id_msg = msg['user_id']
        message_text = msg['message_text']
        has_reply = db.has_reply(message_id)

        message_list += f"ID: {message_id}\n"
        message_list += f"От пользователя: {user_id_msg}\n"
        message_list += f"Сообщение: {message_text[:100]}{'...' if len(message_text) > 100 else ''}\n"
        message_list += f"Статус: {'✅ Отвечено' if has_reply else '⏳ Ожидает ответа'}\n\n"

    if len(messages) > 10:
        message_list += f"\n... и еще {len(messages) - 10} сообщений\n"
        message_list += "\n🌐 Откройте веб-интерфейс для просмотра всех сообщений: http://localhost:5001"

    await update.message.reply_text(message_list)


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /cancel"""
    user_id = update.effective_user.id

    if user_id in user_message:
        del user_message[user_id]

    if user_id in admin_awaiting_reply:
        del admin_awaiting_reply[user_id]

    await update.message.reply_text("❌ Операция отменена")
    return ConversationHandler.END


async def test_error_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для тестирования системы отправки ошибок (только для администратора)"""
    user_id = update.effective_user.id

    # Проверяем, что это администратор для отчетов об ошибках
    if user_id != ERROR_REPORT_ADMIN_ID:
        await update.message.reply_text("❌ Эта команда доступна только администратору")
        return

    await update.message.reply_text("🧪 Тестирование системы отправки ошибок...\n\n1. Отправка WARNING...")

    # Тестируем WARNING
    logger.warning("Это тестовое предупреждение (WARNING)")

    await update.message.reply_text("2. Отправка ERROR...")

    # Тестируем ERROR
    logger.error("Это тестовая ошибка (ERROR)")

    await update.message.reply_text("3. Генерация исключения...")

    # Тестируем обработчик исключений
    try:
        # Намеренно вызываем ошибку
        raise ValueError("Это тестовое исключение для проверки error_handler")
    except Exception as e:
        # Передаем в error_handler
        await error_handler(update, context)

    await update.message.reply_text("✅ Тестирование завершено! Проверьте, пришли ли сообщения об ошибках.")


async def handle_any_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик всех текстовых сообщений от пользователей (не команд)

    ВАЖНО: Этот обработчик вызывается ТОЛЬКО если ConversationHandler не обработал сообщение.
    Это означает, что если админ находится в состоянии WAITING_FOR_REPLY или WAITING_FOR_MESSAGE,
    то ConversationHandler обработает сообщение первым, и этот обработчик не будет вызван.
    """
    user = update.effective_user
    user_id = user.id

    # Получаем список получателей
    recipients = get_recipients()

    # Если это сообщение от одного из получателей (администраторов), игнорируем
    # Это сообщение не должно обрабатываться как анонимное сообщение от пользователя
    if user_id in recipients:
        logger.debug(f"Игнорируем сообщение от получателя {user_id} (не в состоянии разговора)")
        return

    # Если это сообщение из группы, игнорируем
    if update.message.chat.type in ['group', 'supergroup']:
        logger.debug(f"Игнорируем сообщение из группы {update.message.chat.id}")
        return

    message_text = update.message.text

    # Обновляем информацию о пользователе
    db.add_or_update_user(
        user_id=user_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        full_name=user.full_name,
        is_bot=user.is_bot,
        is_premium=user.is_premium if hasattr(user, 'is_premium') else False,
        language_code=user.language_code
    )

    # Генерируем уникальный ID для сообщения
    message_id = generate_message_id()

    # Сохраняем сообщение в базу данных
    db.add_message(
        message_id=message_id,
        user_id=user_id,
        message_text=message_text,
        is_from_admin=False
    )

    # Формируем информацию о пользователе
    user_info = format_user_info(user)

    # Создаем кнопку "Ответить"
    keyboard = [[InlineKeyboardButton("💬 Ответить", callback_data=f"reply_{message_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем сообщение всем получателям
    try:
        message_text_formatted = f"📩 Новое сообщение:\n\n{user_info}\n\n📝 Текст:\n{message_text}\n\n🔑 Message ID: <code>{message_id}</code>"
        success_count, failed = await send_to_all_recipients(
            context=context,
            text=message_text_formatted,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

        logger.info(f"Сообщение {message_id} от пользователя {user_id} отправлено {success_count} получателям")
        if failed:
            logger.warning(f"⚠️ Не удалось отправить получателям: {failed}")

        # Подтверждаем пользователю
        if success_count > 0:
            await update.message.reply_text(
                "✅ Ваше анонимное сообщение отправлено!\n"
                "Ожидайте ответа."
            )
        else:
            await update.message.reply_text(
                "❌ Произошла ошибка при отправке сообщения. Попробуйте позже."
            )

    except Exception as e:
        logger.error(f"Ошибка при отправке анонимного сообщения: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при отправке сообщения. Попробуйте позже."
        )


def main() -> None:
    """Запуск бота"""
    # Получаем токен из переменной окружения
    token = os.getenv('TELEGRAM_BOT_TOKEN')

    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не установлен в .env файле!")
        return

    if not os.getenv('ADMIN_ID'):
        logger.error("ADMIN_ID не установлен в .env файле!")
        return

    logger.info("✅ База данных SQLite готова к работе")

    # Создаем приложение
    application = Application.builder().token(token).build()

    # Сохраняем application глобально для TelegramLogHandler
    global _bot_application
    _bot_application = application

    # Добавляем Telegram обработчик для логов (WARNING и ERROR)
    telegram_handler = TelegramLogHandler(ERROR_REPORT_ADMIN_ID)
    telegram_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(telegram_handler)

    # Также добавляем для root logger, чтобы ловить ошибки из других модулей
    logging.getLogger().addHandler(telegram_handler)

    logger.info(f"✅ Telegram обработчик логов настроен для администратора {ERROR_REPORT_ADMIN_ID}")

    # Добавляем обработчик ConversationHandler для отправки сообщений
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("send", send_command),
            CallbackQueryHandler(reply_button_pressed, pattern="^reply_")
        ],
        states={
            WAITING_FOR_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_message),
                CommandHandler("cancel", cancel_command),
            ],
            WAITING_FOR_REPLY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_reply),
                CommandHandler("cancel", cancel_command),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        per_message=False,
        per_chat=True,
        per_user=True,
    )

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("myid", myid_command))
    application.add_handler(CommandHandler("messages", messages_command))
    application.add_handler(CommandHandler("test_error", test_error_command))

    # ВАЖНО: ConversationHandler должен быть зарегистрирован ПЕРЕД общим обработчиком
    # Это гарантирует, что сообщения в состоянии разговора обрабатываются правильно
    application.add_handler(conv_handler)

    # Обработчик всех текстовых сообщений (должен быть последним!)
    # ConversationHandler имеет приоритет, поэтому этот обработчик сработает
    # только если пользователь НЕ находится в состоянии разговора
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_any_message))

    # Регистрируем обработчик ошибок
    application.add_error_handler(error_handler)
    logger.info("✅ Обработчик ошибок зарегистрирован")

    # Запускаем бота
    logger.info("🤖 Бот запущен...")
    application.run_polling()


if __name__ == '__main__':
    main()
