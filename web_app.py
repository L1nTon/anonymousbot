#!/usr/bin/env python3
"""
Web Interface для Anonymous Bot
Веб-интерфейс для управления анонимными сообщениями
Версия 2.0 с SQLite базой данных
"""

import os
import asyncio
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from telegram import Bot
from database import Database

# Загружаем переменные окружения
load_dotenv()

app = Flask(__name__)
CORS(app)

# Инициализация базы данных
db = Database()

# Telegram Bot
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))


@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')


@app.route('/api/chats')
def get_chats():
    """Получить список всех чатов (пользователей)"""
    chats_data = db.get_chats_with_last_message()

    # Форматируем данные для фронтенда
    chats_list = []
    for chat in chats_data:
        user_info = {
            "user_id": chat['user_id'],
            "username": chat['username'] or "N/A",
            "first_name": chat['first_name'] or "N/A",
            "last_name": chat['last_name'] or "N/A",
            "full_name": chat['full_name'] or f"User {chat['user_id']}",
        }

        # Получаем сообщения пользователя
        messages = db.get_user_messages(chat['user_id'])

        # Форматируем сообщения
        formatted_messages = []
        for msg in messages:
            # Получаем ответы на это сообщение
            replies = db.get_message_replies(msg['message_id'])

            formatted_msg = {
                "message_id": msg['message_id'],
                "text": msg['message_text'],
                "timestamp": msg['timestamp'],
                "is_from_admin": bool(msg['is_from_admin']),
                "replies": []
            }

            # Добавляем ответы
            for reply in replies:
                formatted_msg["replies"].append({
                    "reply_text": reply['reply_text'],
                    "timestamp": reply['timestamp'],
                    "admin_id": reply['admin_id']
                })

            formatted_messages.append(formatted_msg)

        chat_item = {
            "user_id": chat['user_id'],
            "user_info": user_info,
            "messages": formatted_messages,
            "unread_count": chat['unread_count'],
            "last_message_time": chat['last_message_time'],
            "last_seen": chat['last_seen']
        }

        chats_list.append(chat_item)

    return jsonify(chats_list)


@app.route('/api/messages/<int:user_id>')
def get_messages(user_id):
    """Получить все сообщения от конкретного пользователя"""
    messages = db.get_user_messages(user_id)
    user = db.get_user(user_id)

    formatted_messages = []
    for msg in messages:
        # Получаем ответы на это сообщение
        replies = db.get_message_replies(msg['message_id'])

        formatted_msg = {
            "message_id": msg['message_id'],
            "text": msg['message_text'],
            "timestamp": msg['timestamp'],
            "is_from_admin": bool(msg['is_from_admin']),
            "user_info": {
                "user_id": user['user_id'],
                "username": user['username'] or "N/A",
                "first_name": user['first_name'] or "N/A",
                "last_name": user['last_name'] or "N/A",
                "full_name": user['full_name'] or f"User {user['user_id']}",
            } if user else {},
            "replies": []
        }

        # Добавляем ответы
        for reply in replies:
            formatted_msg["replies"].append({
                "reply_text": reply['reply_text'],
                "timestamp": reply['timestamp'],
                "admin_id": reply['admin_id']
            })

        formatted_messages.append(formatted_msg)

    return jsonify(formatted_messages)


@app.route('/api/send_reply', methods=['POST'])
def send_reply():
    """Отправить ответ пользователю"""
    data = request.json
    message_id = data.get('message_id')
    reply_text = data.get('reply_text')

    if not message_id or not reply_text:
        return jsonify({"success": False, "error": "Не указан message_id или reply_text"}), 400

    # Получаем сообщение из базы данных
    message = db.get_message(message_id)
    if not message:
        return jsonify({"success": False, "error": "Сообщение не найдено"}), 404

    user_id = message['user_id']

    try:
        # Отправляем сообщение через Telegram Bot
        bot = Bot(token=BOT_TOKEN)

        # Используем asyncio для отправки сообщения
        async def send_message():
            await bot.send_message(
                chat_id=user_id,
                text=f"💬 Ответ на ваше анонимное сообщение:\n\n{reply_text}"
            )

        # Запускаем асинхронную функцию
        asyncio.run(send_message())

        # Сохраняем ответ в базу данных
        db.add_admin_reply(
            message_id=message_id,
            admin_id=ADMIN_ID,
            reply_text=reply_text
        )

        return jsonify({"success": True, "message": "Ответ отправлен!"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/send_message', methods=['POST'])
def send_message():
    """Отправить новое сообщение пользователю от имени администратора"""
    data = request.json
    user_id = data.get('user_id')
    message_text = data.get('message_text')

    if not user_id or not message_text:
        return jsonify({"success": False, "error": "Не указан user_id или message_text"}), 400

    try:
        # Отправляем сообщение через Telegram Bot
        bot = Bot(token=BOT_TOKEN)

        # Используем asyncio для отправки сообщения
        async def send_msg():
            await bot.send_message(
                chat_id=user_id,
                text=f"📩 Новое сообщение:\n\n{message_text}"
            )

        # Запускаем асинхронную функцию
        asyncio.run(send_msg())

        # Сохраняем сообщение в базу данных как сообщение от администратора
        import uuid
        message_id = str(uuid.uuid4())[:8]
        db.add_message(
            message_id=message_id,
            user_id=user_id,
            message_text=message_text,
            is_from_admin=True
        )

        return jsonify({"success": True, "message": "Сообщение отправлено!"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/stats')
def get_stats():
    """Получить статистику"""
    stats = db.get_stats()
    return jsonify(stats)


if __name__ == '__main__':
    import sys
    port = 5000

    # Проверяем, свободен ли порт
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()

    if result == 0:
        print(f"⚠️  Порт {port} занят, пробуем порт 5001...")
        port = 5001

    print("🌐 Запуск веб-интерфейса...")
    print(f"📍 Откройте в браузере: http://localhost:{port}")
    app.run(debug=True, host='0.0.0.0', port=port, use_reloader=False)

