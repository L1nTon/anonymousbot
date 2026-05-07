#!/usr/bin/env python3
"""
Web Interface для Anonymous Bot
Веб-интерфейс для управления анонимными сообщениями
Версия 2.0 с SQLite базой данных
"""

import os
import asyncio
import mimetypes
from io import BytesIO
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, abort
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
_admin_id_raw = os.getenv('ADMIN_ID')
try:
    ADMIN_ID = int(_admin_id_raw) if _admin_id_raw else 0
except ValueError:
    ADMIN_ID = 0
    print("⚠️  ADMIN_ID в .env должен быть числом")

if not BOT_TOKEN:
    print("⚠️  TELEGRAM_BOT_TOKEN не задан в .env — отправка сообщений работать не будет")


@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')


def _format_message(msg, include_user_info=False, user=None):
    """Универсальное форматирование строки сообщения для фронта."""
    replies = db.get_message_replies(msg['message_id'])
    out = {
        "message_id": msg['message_id'],
        "text": msg.get('message_text') or '',
        "timestamp": msg['timestamp'],
        "is_from_admin": bool(msg.get('is_from_admin')),
        "media_type": msg.get('media_type'),
        "has_media": bool(msg.get('file_id')),
        "caption": msg.get('caption'),
        "replies": [
            {
                "reply_text": r.get('reply_text') or '',
                "timestamp": r['timestamp'],
                "admin_id": r['admin_id'],
                "media_type": r.get('media_type'),
                "has_media": bool(r.get('file_id')),
                "caption": r.get('caption'),
                # ID нужен фронту, чтобы запросить /api/media/reply/<id>
                "reply_id": r.get('id'),
            }
            for r in replies
        ],
    }
    if include_user_info and user:
        out["user_info"] = {
            "user_id": user['user_id'],
            "username": user['username'] or "N/A",
            "first_name": user['first_name'] or "N/A",
            "last_name": user['last_name'] or "N/A",
            "full_name": user['full_name'] or f"User {user['user_id']}",
        }
    return out


@app.route('/api/chats')
def get_chats():
    """Получить список всех чатов (пользователей)"""
    chats_data = db.get_chats_with_last_message()

    chats_list = []
    for chat in chats_data:
        user_info = {
            "user_id": chat['user_id'],
            "username": chat['username'] or "N/A",
            "first_name": chat['first_name'] or "N/A",
            "last_name": chat['last_name'] or "N/A",
            "full_name": chat['full_name'] or f"User {chat['user_id']}",
        }

        messages = db.get_user_messages(chat['user_id'])
        formatted_messages = [_format_message(m) for m in messages]

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

    formatted_messages = [
        _format_message(m, include_user_info=True, user=user) for m in messages
    ]
    return jsonify(formatted_messages)


# ----- Раздача медиа-файлов из Telegram -----

_MEDIA_MIMES = {
    'photo': ('image/jpeg', '.jpg'),
    'video': ('video/mp4', '.mp4'),
    'animation': ('image/gif', '.gif'),
    'audio': ('audio/mpeg', '.mp3'),
    'voice': ('audio/ogg', '.ogg'),
    'video_note': ('video/mp4', '.mp4'),
    'sticker': ('image/webp', '.webp'),
    'document': ('application/octet-stream', ''),
}


def _download_telegram_file(file_id: str) -> bytes:
    """Синхронно скачивает файл из Telegram по file_id."""
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")

    async def _fetch():
        bot = Bot(token=BOT_TOKEN)
        f = await bot.get_file(file_id)
        bio = BytesIO()
        await f.download_to_memory(out=bio)
        return bio.getvalue()

    return asyncio.run(_fetch())


@app.route('/api/media/message/<message_id>')
def get_message_media(message_id):
    """Отдаёт медиафайл сообщения пользователя"""
    msg = db.get_message(message_id)
    if not msg or not msg.get('file_id'):
        abort(404)

    try:
        data = _download_telegram_file(msg['file_id'])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    mime, ext = _MEDIA_MIMES.get(
        msg.get('media_type') or '',
        ('application/octet-stream', '')
    )
    filename = f"{message_id}{ext}" if ext else message_id
    return send_file(BytesIO(data), mimetype=mime, as_attachment=False,
                     download_name=filename)


@app.route('/api/media/reply/<int:reply_id>')
def get_reply_media(reply_id):
    """Отдаёт медиафайл ответа администратора"""
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM admin_replies WHERE id = ?", (reply_id,))
    row = cur.fetchone()
    conn.close()
    if not row or not row['file_id']:
        abort(404)

    try:
        data = _download_telegram_file(row['file_id'])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    mime, ext = _MEDIA_MIMES.get(
        row['media_type'] or '',
        ('application/octet-stream', '')
    )
    filename = f"reply_{reply_id}{ext}" if ext else f"reply_{reply_id}"
    return send_file(BytesIO(data), mimetype=mime, as_attachment=False,
                     download_name=filename)


@app.route('/api/send_reply', methods=['POST'])
def send_reply():
    """Отправить ответ пользователю"""
    data = request.json
    message_id = data.get('message_id')
    reply_text = data.get('reply_text')

    if not message_id or not reply_text:
        return jsonify({"success": False, "error": "Не указан message_id или reply_text"}), 400

    if not BOT_TOKEN:
        return jsonify({"success": False, "error": "TELEGRAM_BOT_TOKEN не задан"}), 500

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

    if not BOT_TOKEN:
        return jsonify({"success": False, "error": "TELEGRAM_BOT_TOKEN не задан"}), 500

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
    # debug=False по умолчанию для безопасности; включите DEBUG=1 в окружении для разработки
    debug_mode = os.getenv('DEBUG', '0') == '1'
    app.run(debug=debug_mode, host='0.0.0.0', port=port, use_reloader=False)

