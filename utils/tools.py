# utils/tools.py

import logging
import random

MAX_MESSAGE_LENGTH = 4000

logger = logging.getLogger("SUPPERTIME.tools")

def split_for_telegram(text: str, max_length: int = MAX_MESSAGE_LENGTH):
    """
    Split text into chunks suitable for Telegram.
    - Предпочитает резать по '\n'
    - Если нет переносов, пытается резать по пробелам
    - Если и пробелов нет (одно длинное слово) — рубит жёстко по символам
    """
    parts = []
    text = (text or "").strip()

    while len(text) > max_length:
        idx = text.rfind('\n', 0, max_length)
        if idx == -1:
            idx = text.rfind(' ', 0, max_length)
        if idx == -1:
            logger.warning("Hard split at max_length (no spaces/newlines).")
            idx = max_length
        parts.append(text[:idx])
        text = text[idx:].lstrip('\n ')
    if text:
        parts.append(text)
    return parts or [""]


def send_long_message(chat_id, text, send_func, reply_to_message_id=None):
    """
    Send long text by splitting into multiple Telegram messages.
    - Разбивает текст на части
    - Пытается отправить все части
    - Логирует ошибки, если send_func падает
    """
    parts = split_for_telegram(text)
    sent = 0
    for part in parts:
        try:
            send_func(chat_id, part, reply_to_message_id=reply_to_message_id)
            sent += 1
        except Exception as e:
            logger.error(f"Failed to send Telegram message part: {e}")
        reply_to_message_id = None  # reply только на первый кусок
    return sent