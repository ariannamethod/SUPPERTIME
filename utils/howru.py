import os
import random
import threading
import time
from openai import OpenAI

GREETINGS_RU = [
    "Эй, как дела?", "Привет! Что нового?", "Хэй, как ты?", "Как настроение?"
]
GREETINGS_EN = [
    "Hey, how are you?", "Hi there, all good?", "Hello! How's it going?", "Yo, how's life?"
]

COMMON_GREETINGS = [
    "привет",
    "как дела",
    "hello",
    "hi",
    "hey",
    "здравствуйте",
    "how are you",
    "how's it going",
    "доброе утро",
    "добрый день",
    "добрый вечер",
    "good morning",
    "good afternoon",
    "good evening",
]

DEFAULT_TOPICS = [
    "планы на выходные",
    "любимые книги",
    "новые фильмы",
    "путешествия",
    "музыку, которую ты слушаешь",
    "weekend plans",
    "favorite books",
    "recent movies",
    "travel",
    "music you're into",
]

FALLBACK_MESSAGES = [
    "Привет! Как проходит твой день?",
    "Hey there! How's your day going?",
]

api_key = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=api_key) if api_key else None


def _clean_message(msg: str) -> str:
    text = msg.lower()
    for phrase in COMMON_GREETINGS:
        text = text.replace(phrase, "")
    return " ".join(text.split()).strip()


def _summarize_context(history):
    if not openai_client:
        return None
    cleaned = [_clean_message(m) for m in history if _clean_message(m)]
    if not cleaned:
        return None
    recent = "\n".join(cleaned[-5:])
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "Summarize the conversation context in 5-10 words."},
                {"role": "user", "content": recent},
            ],
            max_tokens=40,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return None

MIN_THEME_WORDS = 2


def _craft_greeting(history):
    if not history:
        return random.choice(GREETINGS_RU + GREETINGS_EN)

    theme = None
    for msg in reversed(history):
        cleaned = _clean_message(msg)
        if not cleaned:
            continue
        if cleaned in COMMON_GREETINGS or len(cleaned.split()) < MIN_THEME_WORDS:
            continue
        theme = " ".join(cleaned.split()[:5])
        break

    if not theme and len(history) > 2 and random.random() < 0.5:
        summary = _summarize_context(history)
        if summary:
            theme = summary

    if not theme:
        theme = random.choice(DEFAULT_TOPICS) if DEFAULT_TOPICS else None

    if not theme:
        return random.choice(FALLBACK_MESSAGES)

    if any(c in theme for c in "ёйцукенгшщзхъфывапролджэячсмитьбю"):
        return f"Привет, как дела? Я помню нашу тему: {theme}..."
    return f"Hey, how's it going? Remember we talked about {theme}?"


def schedule_howru(get_users, get_history, send_func):
    """Periodically send a friendly check-in to random users."""
    def _loop():
        while True:
            # wait between 2 and 4 hours
            time.sleep(random.uniform(7200, 14400))
            if random.random() < 0.2:
                users = get_users()
                if not users:
                    continue
                chat_id = random.choice(users)
                history = get_history(chat_id)
                msg = _craft_greeting(history)
                send_func(chat_id, msg)
    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    return thread
