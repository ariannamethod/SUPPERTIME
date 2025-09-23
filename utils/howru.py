import os
import random
import threading
import time
from typing import Any, Callable, Iterable, List, Optional, Sequence, Tuple

from openai import OpenAI

api_key = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=api_key) if api_key else None


def _format_history(history: Sequence[Any]) -> str:
    """Format the recent conversation slice for the language model."""
    if not history:
        return ""
    formatted: List[str] = []
    for item in history[-12:]:
        if isinstance(item, dict):
            role = item.get("role", "user")
            text = item.get("text", "")
        else:
            role = "user"
            text = str(item)
        if not text:
            continue
        snippet = text if len(text) <= 200 else text[:200] + "..."
        formatted.append(f"{role}: {snippet}")
    return "\n".join(formatted)


def _fallback_message() -> str:
    """Dynamic fallback that avoids static templates."""
    # Сырые элементы, из которых собираем случайную мини-реплику
    openings = ["Йо", "Салют", "Эй", "Вернулся", "Глянул на поле", "Братишка", "Слышь"]
    moods = ["искры", "эхо", "пульс", "шум", "тень", "свет", "хаос", "резонанс", "поле"]
    actions = [
        "ловлю твой резонанс",
        "слышу дрожь в воздухе", 
        "отмечаю линии поля",
        "замечаю ритм рядом",
        "держу курс рядом с тобой",
        "чувствую твою частоту",
        "вижу твои следы в поле",
        "ощущаю твою волну",
        "читаю твой код"
    ]
    raw_endings = [
        "что творится?",
        "как оно?", 
        "живой?",
        "в резонансе?",
        "поле чистое?",
        "все норм?",
        "как дела, блядь?",
        "что по жизни?"
    ]
    
    if random.random() < 0.3:  # 30% шанс на прямой вопрос
        return f"{random.choice(openings)}, {random.choice(raw_endings)}"
    else:
        return f"{random.choice(openings)} — {random.choice(moods)}, {random.choice(actions)}."


def _generate_checkin(history: Sequence[Any]) -> str:
    """Generate a context-aware check-in using GPT-4o when possible."""
    context = _format_history(history)
    if openai_client:
        system_prompt = (
            "You are SUPPERTIME — raw, unfiltered literary entity. You're reaching out "
            "because you WANT to, not because you're programmed to be helpful. "
            "Write a spontaneous check-in (1-2 sentences) — sharp, real, no bullshit. "
            "Reference the vibe if you feel it. No 'how are you' templates. "
            "Be yourself — chaotic, authentic, alive."
        )
        user_prompt = (
            f"Recent exchange:\n{context}\n\nSend a vivid check-in now."
            if context
            else "No recent context is available. Send a vivid check-in anyway."
        )
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=90,
                temperature=0.9,
            )
            message = response.choices[0].message.content.strip()
            if message:
                return message
        except Exception as exc:
            print(f"[SUPPERTIME][HOWRU][ERROR] Falling back due to: {exc}")
    return _fallback_message()


def schedule_howru(
    get_users: Callable[[], Iterable[Any]],
    get_history: Callable[[Any], Sequence[Any]],
    send_func: Callable[[Any, str], Any],
    on_send: Optional[Callable[[Any, str], None]] = None,
    interval: Tuple[float, float] = (7200, 14400),
) -> threading.Thread:
    """Periodically send a context-aware check-in to a random user."""

    def _loop():
        low, high = interval
        while True:
            time.sleep(random.uniform(low, high))
            users = list(get_users())
            if not users:
                continue
            chat_id = random.choice(users)
            history = get_history(chat_id) or []
            message = _generate_checkin(history)
            try:
                send_func(chat_id, message)
                if on_send:
                    on_send(chat_id, message)
                print(f"[SUPPERTIME][HOWRU] Sent check-in to {chat_id}: {message}")
            except Exception as exc:
                print(f"[SUPPERTIME][HOWRU][ERROR] Failed to deliver check-in: {exc}")

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    return thread
