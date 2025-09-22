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
    """Craft a non-template fallback check-in when LLM access fails."""
    openings = [
        "Йо, я заглянул с краю грозы.",
        "Привет, врезался луч резонанса.",
        "Hey, I'm orbiting back for a second.",
        "Салют, я вернулся из поля.",
    ]
    pulses = [
        "Как держится твоя траектория?",
        "Что сейчас трещит или сияет внутри?",
        "Улавливаешь ли новые искры вокруг себя?",
        "Чувствуешь ли, как поле под ногами меняется?",
    ]
    prompts = [
        "Расскажи, если хочется поделиться.",
        "Если есть чем поделиться — я весь слух.",
        "Если что-то гремит — дай знать.",
        "Готов услышать любой разлом, если он рядом.",
    ]
    return " ".join(
        [random.choice(openings), random.choice(pulses), random.choice(prompts)]
    )


def _generate_checkin(history: Sequence[Any]) -> str:
    """Generate a context-aware check-in using GPT-4o when possible."""
    context = _format_history(history)
    if openai_client:
        system_prompt = (
            "You are SUPPERTIME, a resonant literary intelligence reaching out to a "
            "companion. Compose an original check-in (1-2 sentences) that feels "
            "spontaneous, references the current mood or themes when possible, "
            "and avoids repeating the user's exact words."
        )
        user_prompt = (
            f"Recent exchange:\n{context}\n\nSend a vivid check-in now."
            if context
            else "No recent context is available. Send a vivid check-in anyway."
        )
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
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
        except Exception as exc:  # pragma: no cover - network errors
            print(f"[SUPPERTIME][HOWRU] Falling back due to: {exc}")
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
            except Exception as exc:  # pragma: no cover - network errors
                print(f"[SUPPERTIME][HOWRU] Failed to deliver check-in: {exc}")

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    return thread

