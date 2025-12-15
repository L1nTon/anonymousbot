#!/usr/bin/env python3
"""
Database module для Anonymous Bot
Работа с SQLite базой данных
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any


class Database:
    """Класс для работы с SQLite базой данных"""
    
    def __init__(self, db_path: str = "anonymous_bot.db"):
        """Инициализация базы данных"""
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Получить соединение с базой данных"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Для доступа к колонкам по имени
        return conn
    
    def init_database(self):
        """Создать таблицы, если их нет"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                full_name TEXT,
                is_bot INTEGER DEFAULT 0,
                is_premium INTEGER DEFAULT 0,
                language_code TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица сообщений
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                message_text TEXT NOT NULL,
                message_length INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                admin_message_id INTEGER,
                is_from_admin INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Таблица ответов администратора
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL,
                admin_id INTEGER NOT NULL,
                reply_text TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES messages(message_id)
            )
        """)
        
        # Индексы для быстрого поиска
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_admin_replies_message_id ON admin_replies(message_id)")
        
        conn.commit()
        conn.close()
    
    # ==================== ПОЛЬЗОВАТЕЛИ ====================
    
    def add_or_update_user(self, user_id: int, username: str = None, first_name: str = None,
                          last_name: str = None, full_name: str = None, is_bot: bool = False,
                          is_premium: bool = False, language_code: str = None):
        """Добавить или обновить пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Безопасное преобразование в int (обработка None)
        is_bot_int = int(is_bot) if is_bot is not None else 0
        is_premium_int = int(is_premium) if is_premium is not None else 0

        cursor.execute("""
            INSERT INTO users (user_id, username, first_name, last_name, full_name,
                             is_bot, is_premium, language_code, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                full_name = excluded.full_name,
                is_bot = excluded.is_bot,
                is_premium = excluded.is_premium,
                language_code = excluded.language_code,
                last_seen = CURRENT_TIMESTAMP
        """, (user_id, username, first_name, last_name, full_name,
              is_bot_int, is_premium_int, language_code))
        
        conn.commit()
        conn.close()
    
    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить информацию о пользователе"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """Получить всех пользователей"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users ORDER BY last_seen DESC")
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    # ==================== СООБЩЕНИЯ ====================
    
    def add_message(self, message_id: str, user_id: int, message_text: str,
                   admin_message_id: int = None, is_from_admin: bool = False) -> bool:
        """Добавить сообщение"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO messages (message_id, user_id, message_text, message_length,
                                    admin_message_id, is_from_admin)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (message_id, user_id, message_text, len(message_text),
                  admin_message_id, int(is_from_admin)))

            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Получить сообщение по ID"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM messages WHERE message_id = ?", (message_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def get_user_messages(self, user_id: int) -> List[Dict[str, Any]]:
        """Получить все сообщения пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM messages
            WHERE user_id = ?
            ORDER BY timestamp ASC
        """, (user_id,))
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_all_messages(self) -> List[Dict[str, Any]]:
        """Получить все сообщения"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM messages ORDER BY timestamp DESC")
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    # ==================== ОТВЕТЫ АДМИНИСТРАТОРА ====================

    def add_admin_reply(self, message_id: str, admin_id: int, reply_text: str) -> bool:
        """Добавить ответ администратора"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO admin_replies (message_id, admin_id, reply_text)
                VALUES (?, ?, ?)
            """, (message_id, admin_id, reply_text))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Ошибка при добавлении ответа: {e}")
            return False

    def get_message_replies(self, message_id: str) -> List[Dict[str, Any]]:
        """Получить все ответы на сообщение"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM admin_replies
            WHERE message_id = ?
            ORDER BY timestamp ASC
        """, (message_id,))
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def has_reply(self, message_id: str) -> bool:
        """Проверить, есть ли ответ на сообщение"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) as count FROM admin_replies WHERE message_id = ?
        """, (message_id,))
        row = cursor.fetchone()
        conn.close()

        return row['count'] > 0

    # ==================== ЧАТЫ (для веб-интерфейса) ====================

    def get_chats_with_last_message(self) -> List[Dict[str, Any]]:
        """Получить список всех чатов с последним сообщением"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                u.user_id,
                u.username,
                u.first_name,
                u.last_name,
                u.full_name,
                u.last_seen,
                (SELECT message_text FROM messages WHERE user_id = u.user_id
                 ORDER BY timestamp DESC LIMIT 1) as last_message,
                (SELECT timestamp FROM messages WHERE user_id = u.user_id
                 ORDER BY timestamp DESC LIMIT 1) as last_message_time,
                (SELECT COUNT(*) FROM messages WHERE user_id = u.user_id
                 AND message_id NOT IN (SELECT message_id FROM admin_replies)) as unread_count
            FROM users u
            ORDER BY COALESCE(last_message_time, u.last_seen) DESC
        """)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    # ==================== СТАТИСТИКА ====================

    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Общее количество пользователей
        cursor.execute("SELECT COUNT(*) as count FROM users")
        total_users = cursor.fetchone()['count']

        # Общее количество сообщений
        cursor.execute("SELECT COUNT(*) as count FROM messages WHERE is_from_admin = 0")
        total_messages = cursor.fetchone()['count']

        # Количество отвеченных сообщений
        cursor.execute("""
            SELECT COUNT(DISTINCT message_id) as count FROM admin_replies
        """)
        answered_messages = cursor.fetchone()['count']

        # Количество неотвеченных сообщений
        unanswered_messages = total_messages - answered_messages

        conn.close()

        return {
            "total_users": total_users,
            "total_messages": total_messages,
            "answered_messages": answered_messages,
            "unanswered_messages": unanswered_messages
        }

    # ==================== УТИЛИТЫ ====================

    def clear_all_data(self):
        """Очистить все данные (для тестирования)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM admin_replies")
        cursor.execute("DELETE FROM messages")
        cursor.execute("DELETE FROM users")

        conn.commit()
        conn.close()
        print("✅ Все данные удалены из базы данных")

