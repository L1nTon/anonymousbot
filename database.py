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
        """Получить соединение с базой данных.

        check_same_thread=False позволяет использовать соединение в разных потоках
        Flask. Поскольку для каждого вызова мы открываем и закрываем своё соединение,
        это безопасно.
        """
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Для доступа к колонкам по имени
        # Включаем foreign keys (по умолчанию выключены в SQLite)
        conn.execute("PRAGMA foreign_keys = ON")
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
                message_text TEXT,
                message_length INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                admin_message_id INTEGER,
                is_from_admin INTEGER DEFAULT 0,
                media_type TEXT,
                file_id TEXT,
                file_unique_id TEXT,
                caption TEXT,
                tg_message_id INTEGER,
                tg_chat_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Таблица ответов администратора
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL,
                admin_id INTEGER NOT NULL,
                reply_text TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                media_type TEXT,
                file_id TEXT,
                file_unique_id TEXT,
                caption TEXT,
                FOREIGN KEY (message_id) REFERENCES messages(message_id)
            )
        """)

        # Индексы для быстрого поиска
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_admin_replies_message_id ON admin_replies(message_id)")

        # ---- Миграция: для старых БД добавляем недостающие колонки ----
        self._migrate_add_column(cursor, "messages", "media_type", "TEXT")
        self._migrate_add_column(cursor, "messages", "file_id", "TEXT")
        self._migrate_add_column(cursor, "messages", "file_unique_id", "TEXT")
        self._migrate_add_column(cursor, "messages", "caption", "TEXT")
        self._migrate_add_column(cursor, "messages", "tg_message_id", "INTEGER")
        self._migrate_add_column(cursor, "messages", "tg_chat_id", "INTEGER")
        self._migrate_add_column(cursor, "admin_replies", "media_type", "TEXT")
        self._migrate_add_column(cursor, "admin_replies", "file_id", "TEXT")
        self._migrate_add_column(cursor, "admin_replies", "file_unique_id", "TEXT")
        self._migrate_add_column(cursor, "admin_replies", "caption", "TEXT")

        conn.commit()
        conn.close()

    @staticmethod
    def _migrate_add_column(cursor, table: str, column: str, col_type: str):
        """Безопасно добавляет колонку в таблицу, если её ещё нет."""
        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        if column not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    
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
    
    def add_message(self, message_id: str, user_id: int,
                    message_text: Optional[str] = None,
                    admin_message_id: Optional[int] = None,
                    is_from_admin: bool = False,
                    media_type: Optional[str] = None,
                    file_id: Optional[str] = None,
                    file_unique_id: Optional[str] = None,
                    caption: Optional[str] = None,
                    tg_message_id: Optional[int] = None,
                    tg_chat_id: Optional[int] = None) -> bool:
        """Добавить сообщение (текстовое или с медиа)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            text = message_text or ''

            cursor.execute("""
                INSERT INTO messages (
                    message_id, user_id, message_text, message_length,
                    admin_message_id, is_from_admin,
                    media_type, file_id, file_unique_id, caption,
                    tg_message_id, tg_chat_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message_id, user_id, text, len(text),
                admin_message_id, int(is_from_admin),
                media_type, file_id, file_unique_id, caption,
                tg_message_id, tg_chat_id,
            ))

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

    def add_admin_reply(self, message_id: str, admin_id: int,
                        reply_text: Optional[str] = None,
                        media_type: Optional[str] = None,
                        file_id: Optional[str] = None,
                        file_unique_id: Optional[str] = None,
                        caption: Optional[str] = None) -> bool:
        """Добавить ответ администратора (текст и/или медиа)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO admin_replies (
                    message_id, admin_id, reply_text,
                    media_type, file_id, file_unique_id, caption
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                message_id, admin_id, reply_text or '',
                media_type, file_id, file_unique_id, caption,
            ))

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
        """Получить список всех чатов с последним сообщением.

        unread_count учитывает только сообщения от пользователя (is_from_admin = 0),
        у которых нет ни одного ответа администратора.
        """
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
                (SELECT message_text FROM messages
                 WHERE user_id = u.user_id
                 ORDER BY timestamp DESC LIMIT 1) as last_message,
                (SELECT timestamp FROM messages
                 WHERE user_id = u.user_id
                 ORDER BY timestamp DESC LIMIT 1) as last_message_time,
                (SELECT COUNT(*) FROM messages m
                 WHERE m.user_id = u.user_id
                   AND m.is_from_admin = 0
                   AND NOT EXISTS (
                       SELECT 1 FROM admin_replies r
                       WHERE r.message_id = m.message_id
                   )
                ) as unread_count
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

        # Уникальные пользователи, которые писали сообщения
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) as count
            FROM messages
            WHERE is_from_admin = 0
        """)
        unique_users = cursor.fetchone()['count']

        # Общее количество сообщений (только от пользователей)
        cursor.execute("SELECT COUNT(*) as count FROM messages WHERE is_from_admin = 0")
        total_messages = cursor.fetchone()['count']

        # Отвеченные сообщения (среди пользовательских)
        cursor.execute("""
            SELECT COUNT(DISTINCT m.message_id) as count
            FROM messages m
            INNER JOIN admin_replies r ON r.message_id = m.message_id
            WHERE m.is_from_admin = 0
        """)
        answered_messages = cursor.fetchone()['count']

        unanswered_messages = max(0, total_messages - answered_messages)

        conn.close()

        return {
            "total_users": total_users,
            "unique_users": unique_users,
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

