# utils/memory.py

import os
import json
import sqlite3
import time
import hashlib
import asyncio
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

from utils.journal import log_event, LOG_PATH as JOURNAL_PATH

try:
    from utils import vector_store
except Exception:  # optional dependency
    vector_store = None  # type: ignore

# Путь к SQLite памяти
SUPPERTIME_DATA_PATH = os.getenv("SUPPERTIME_DATA_PATH", "./data")
DB_PATH = os.path.join(SUPPERTIME_DATA_PATH, "suppertime_memory.db")


def _init_db():
    os.makedirs(SUPPERTIME_DATA_PATH, exist_ok=True)
    print(f"[SUPPERTIME][DEBUG] Initializing Memory SQLite database at: {DB_PATH}")
    with sqlite3.connect(DB_PATH) as conn:
        # Старая таблица сводок (совместимость)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL,
                summary TEXT,
                extra TEXT
            )
        """)
        
        # Новые таблицы для расширенной памяти (как у Индианы)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                timestamp TEXT,
                user_message TEXT,
                bot_response TEXT,
                context TEXT,
                metadata TEXT
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_vectors (
                id TEXT PRIMARY KEY,
                content TEXT,
                embedding TEXT,
                user_id TEXT,
                timestamp TEXT,
                memory_type TEXT
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_context (
                user_id TEXT,
                key TEXT,
                value TEXT,
                timestamp TEXT,
                access_count INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, key)
            )
        """)
        
        conn.commit()
    print(f"[SUPPERTIME][DEBUG] Memory SQLite database initialized successfully: {DB_PATH}")


_init_db()


def save_summary(summary: str, extra: Optional[Dict] = None) -> None:
    """Сохраняет сводку в SQLite и в JSON-журнал."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO memory_summaries (ts, summary, extra) VALUES (?, ?, ?)",
                (time.time(), summary, json.dumps(extra or {}, ensure_ascii=False))
            )
            conn.commit()
    except Exception as e:
        print(f"[SUPPERTIME][ERROR] Failed to save summary in DB: {e}")

    # Для обратной совместимости пишем и в журнал
    log_event({"type": "memory_summary", "summary": summary})


def get_recent_summaries(limit: int = 5) -> List[str]:
    """Возвращает последние N сводок (SQLite → fallback JSON)."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT summary FROM memory_summaries ORDER BY ts DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            if rows:
                return [r[0] for r in rows]
    except Exception as e:
        print(f"[SUPPERTIME][WARNING] Failed to read from DB: {e}")

    # fallback: читаем JSON-журнал
    if os.path.exists(JOURNAL_PATH):
        try:
            with open(JOURNAL_PATH, "r", encoding="utf-8") as f:
                log = json.load(f)
            if isinstance(log, list):
                summaries = [e.get("summary", "") for e in log if e.get("type") == "memory_summary"]
                return summaries[-limit:]
        except Exception as e:
            print(f"[SUPPERTIME][WARNING] Failed to read journal: {e}")
    return []


def search_summaries(query: str, limit: int = 5) -> List[str]:
    """Поиск по сводкам (SQLite LIKE)."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT summary FROM memory_summaries WHERE summary LIKE ? ORDER BY ts DESC LIMIT ?",
                (f"%{query}%", limit)
            )
            return [r[0] for r in cursor.fetchall()]
    except Exception as e:
        print(f"[SUPPERTIME][WARNING] Search failed: {e}")
        return []


class ConversationMemory:
    """Собирает сообщения и периодически сводит их в summary."""

    def __init__(self, openai_client: Optional[object] = None, threshold: int = 20):
        self.openai_client = openai_client
        self.threshold = threshold
        self.buffer: List[Dict[str, str]] = []
        self.model = os.getenv("SUPPERTIME_MEMORY_MODEL", "gpt-4o")

    def add_message(self, role: str, content: str) -> None:
        self.buffer.append({"role": role, "content": content})
        if len(self.buffer) >= self.threshold:
            self.summarize()

    def summarize(self) -> str:
        if not self.buffer:
            return ""

        text = "\n".join(f"{m['role']}: {m['content']}" for m in self.buffer)
        summary = text if len(text) < 1500 else text[:1500] + "..."

        if self.openai_client:
            try:
                resp = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "Summarize the following conversation in under 100 words, keeping tone and key context.",
                        },
                        {"role": "user", "content": text},
                    ],
                    max_tokens=200,
                )
                summary = resp.choices[0].message.content.strip()
            except Exception as e:
                print(f"[SUPPERTIME][WARNING] Memory summarization failed: {e}")

        # Сохраняем в SQLite и журнал
        save_summary(summary)

        if vector_store and self.openai_client:
            try:
                api_key = getattr(self.openai_client, "api_key", os.getenv("OPENAI_API_KEY", ""))
                vector_store.add_memory_entry(summary, api_key, {"type": "summary"})
            except Exception as e:
                print(f"[SUPPERTIME][WARNING] Failed to push memory to vector store: {e}")

        self.buffer.clear()
        return summary


class MemoryManager:
    """Улучшенная система памяти как у Индианы - с векторным поиском и контекстом."""
    
    def __init__(self, db_path: str = DB_PATH, vectorstore=None):
        self.db_path = db_path
        self.vectorstore = vectorstore
        self.openai_client = None  # Будет установлен извне
        
    async def __aenter__(self):
        """Async context manager entry."""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass
    
    def _generate_id(self, content: str) -> str:
        """Генерация ID на основе контента."""
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    async def save(self, user_id: str, user_message: str, bot_response: str, context: str = "") -> None:
        """Сохранение диалога в память."""
        try:
            conv_id = self._generate_id(f"{user_id}_{time.time()}_{user_message}")
            timestamp = datetime.now().isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO conversations "
                    "(id, user_id, timestamp, user_message, bot_response, context, metadata) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (conv_id, user_id, timestamp, user_message, bot_response, context, "{}")
                )
                conn.commit()
            
            # Добавляем в векторный поиск (если доступен)
            if self.vectorstore:
                try:
                    # Сохраняем и вопрос и ответ как отдельные векторы
                    await self._add_to_vectors(user_id, user_message, "user_message")
                    await self._add_to_vectors(user_id, bot_response, "bot_response")
                except Exception as e:
                    print(f"[SUPPERTIME][WARNING] Vector storage failed: {e}")
                    
        except Exception as e:
            print(f"[SUPPERTIME][ERROR] Failed to save conversation: {e}")
    
    async def _add_to_vectors(self, user_id: str, content: str, memory_type: str) -> None:
        """Добавление контента в векторное хранилище."""
        if not self.vectorstore or not content.strip():
            return
            
        try:
            vector_id = self._generate_id(f"{user_id}_{content}_{memory_type}")
            timestamp = datetime.now().isoformat()
            
            # Получаем эмбеддинг (заглушка - в реальности нужен OpenAI API)
            embedding = "[]"  # TODO: Реальный эмбеддинг через OpenAI
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO memory_vectors "
                    "(id, content, embedding, user_id, timestamp, memory_type) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (vector_id, content, embedding, user_id, timestamp, memory_type)
                )
                conn.commit()
        except Exception as e:
            print(f"[SUPPERTIME][ERROR] Vector storage failed: {e}")
    
    async def retrieve(self, user_id: str, query: str, limit: int = 5) -> str:
        """Получение релевантного контекста для пользователя."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Ищем последние разговоры пользователя
                cursor = conn.execute(
                    "SELECT user_message, bot_response, timestamp FROM conversations "
                    "WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (user_id, limit)
                )
                conversations = cursor.fetchall()
                
                if not conversations:
                    return ""
                
                # Формируем контекст
                context_parts = []
                for user_msg, bot_resp, ts in conversations:
                    # Упрощенная релевантность - ищем ключевые слова
                    query_words = query.lower().split()
                    user_words = user_msg.lower().split()
                    bot_words = bot_resp.lower().split()
                    
                    relevance = 0
                    for word in query_words:
                        if word in user_words:
                            relevance += 1
                        if word in bot_words:
                            relevance += 1
                    
                    if relevance > 0 or len(context_parts) < 2:  # Всегда берем минимум 2 последних
                        context_parts.append(f"[{ts[:16]}] User: {user_msg}\nSUPPERTIME: {bot_resp}")
                
                return "\n\n".join(context_parts[:3])  # Максимум 3 диалога
                
        except Exception as e:
            print(f"[SUPPERTIME][ERROR] Context retrieval failed: {e}")
            return ""
    
    async def search_memory(self, user_id: str, query: str, limit: int = 3) -> List[str]:
        """Векторный поиск по памяти (упрощенная версия)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Простой текстовый поиск (TODO: заменить на векторный)
                cursor = conn.execute(
                    "SELECT content FROM memory_vectors "
                    "WHERE user_id = ? AND content LIKE ? "
                    "ORDER BY timestamp DESC LIMIT ?",
                    (user_id, f"%{query}%", limit)
                )
                results = [row[0] for row in cursor.fetchall()]
                return results
        except Exception as e:
            print(f"[SUPPERTIME][ERROR] Memory search failed: {e}")
            return []
    
    async def last_response(self, user_id: str) -> str:
        """Получение последнего ответа бота для пользователя."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT bot_response FROM conversations "
                    "WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1",
                    (user_id,)
                )
                row = cursor.fetchone()
                return row[0] if row else ""
        except Exception as e:
            print(f"[SUPPERTIME][ERROR] Last response retrieval failed: {e}")
            return ""
    
    def store_user_context(self, user_id: str, key: str, value: str) -> None:
        """Сохранение пользовательского контекста."""
        try:
            timestamp = datetime.now().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO user_context "
                    "(user_id, key, value, timestamp, access_count) "
                    "VALUES (?, ?, ?, ?, 0)",
                    (user_id, key, value, timestamp)
                )
                conn.commit()
        except Exception as e:
            print(f"[SUPPERTIME][ERROR] Context storage failed: {e}")
    
    def get_user_context(self, user_id: str, key: str) -> Optional[str]:
        """Получение пользовательского контекста."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT value FROM user_context WHERE user_id = ? AND key = ?",
                    (user_id, key)
                )
                row = cursor.fetchone()
                if row:
                    # Увеличиваем счетчик доступа
                    conn.execute(
                        "UPDATE user_context SET access_count = access_count + 1 "
                        "WHERE user_id = ? AND key = ?",
                        (user_id, key)
                    )
                    conn.commit()
                    return row[0]
        except Exception as e:
            print(f"[SUPPERTIME][ERROR] Context retrieval failed: {e}")
        return None
