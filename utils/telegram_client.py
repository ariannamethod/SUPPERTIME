import os
import tempfile
from typing import List, Optional

import requests

from utils.tools import split_for_telegram


class TelegramClient:
    """Simple Telegram Bot API client with common utilities."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.api_url = (
            f"https://api.telegram.org/bot{self.token}" if self.token else None
        )
        self.file_url = (
            f"https://api.telegram.org/file/bot{self.token}" if self.token else None
        )

    def _post(self, method: str, *, json=None, data=None, files=None):
        if not self.api_url:
            print(
                "[SUPPERTIME][WARNING] Telegram bot token not set, cannot send request"
            )
            return None
        url = f"{self.api_url}/{method}"
        try:
            if files:
                response = requests.post(url, data=data, files=files)
            else:
                response = requests.post(url, json=json)
            response.raise_for_status()
            return response
        except Exception as e:
            print(f"[SUPPERTIME][ERROR] Failed Telegram POST {method}: {e}")
            return None

    def _get(self, method: str, *, params=None, full_url=False):
        if not self.api_url and not full_url:
            print(
                "[SUPPERTIME][WARNING] Telegram bot token not set, cannot send request"
            )
            return None
        url = method if full_url else f"{self.api_url}/{method}"
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response
        except Exception as e:
            print(f"[SUPPERTIME][ERROR] Failed Telegram GET {method}: {e}")
            return None

    def send_chat_action(self, chat_id: int, action: str = "typing") -> bool:
        data = {"chat_id": chat_id, "action": action}
        return bool(self._post("sendChatAction", json=data))

    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to_message_id: Optional[int] = None,
        reply_markup: Optional[dict] = None,
    ) -> bool:
        data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        if reply_to_message_id:
            data["reply_to_message_id"] = reply_to_message_id
        if reply_markup:
            data["reply_markup"] = reply_markup
        response = self._post("sendMessage", json=data)
        if response and response.status_code == 200:
            return True
        if response and response.status_code == 400 and "too long" in response.text.lower():
            parts: List[str] = split_for_telegram(text)
            for part in parts:
                self.send_message(chat_id, part, reply_to_message_id)
                reply_to_message_id = None
            return True
        return False

    def send_voice(
        self,
        chat_id: int,
        voice_path: str,
        caption: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
    ) -> bool:
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
        if reply_to_message_id:
            data["reply_to_message_id"] = reply_to_message_id
        try:
            with open(voice_path, "rb") as voice_file:
                files = {"voice": voice_file}
                response = self._post("sendVoice", data=data, files=files)
                return bool(response)
        finally:
            try:
                os.remove(voice_path)
            except Exception:
                pass

    def send_photo(
        self,
        chat_id: int,
        photo_url: str,
        caption: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
    ) -> bool:
        data = {"chat_id": chat_id, "photo": photo_url}
        if caption:
            data["caption"] = caption
        if reply_to_message_id:
            data["reply_to_message_id"] = reply_to_message_id
        response = self._post("sendPhoto", json=data)
        return bool(response)

    def send_keyboard(self, chat_id: int, text: str, keyboard: List[List[dict]]) -> bool:
        reply_markup = {
            "keyboard": keyboard,
            "resize_keyboard": True,
            "one_time_keyboard": True,
        }
        return self.send_message(chat_id, text, reply_markup=reply_markup)

    def set_commands(self, commands: List[dict]) -> bool:
        data = {"commands": commands}
        return bool(self._post("setMyCommands", json=data))

    def answer_callback_query(self, callback_query_id: str) -> bool:
        data = {"callback_query_id": callback_query_id}
        return bool(self._post("answerCallbackQuery", json=data))

    def download_file(self, file_id: str) -> Optional[str]:
        response = self._get("getFile", params={"file_id": file_id})
        if not response:
            return None
        try:
            file_path = response.json()["result"]["file_path"]
            download = self._get(f"{self.file_url}/{file_path}", full_url=True)
            if not download:
                return None
            suffix = "." + file_path.split(".")[-1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(download.content)
                return temp_file.name
        except Exception as e:
            print(f"[SUPPERTIME][ERROR] Failed to download Telegram file: {e}")
            return None


telegram_client = TelegramClient()


def send_chat_action(chat_id: int, action: str = "typing") -> bool:
    return telegram_client.send_chat_action(chat_id, action)


def send_message(chat_id: int, text: str, reply_to_message_id: Optional[int] = None):
    return telegram_client.send_message(chat_id, text, reply_to_message_id)


def send_voice(
    chat_id: int, voice_path: str, caption: Optional[str] = None, reply_to_message_id: Optional[int] = None
):
    return telegram_client.send_voice(chat_id, voice_path, caption, reply_to_message_id)


def send_photo(
    chat_id: int, photo_url: str, caption: Optional[str] = None, reply_to_message_id: Optional[int] = None
):
    return telegram_client.send_photo(chat_id, photo_url, caption, reply_to_message_id)


def send_keyboard(chat_id: int, text: str, keyboard: List[List[dict]]):
    return telegram_client.send_keyboard(chat_id, text, keyboard)


def set_commands(commands: List[dict]):
    return telegram_client.set_commands(commands)


def answer_callback_query(callback_query_id: str):
    return telegram_client.answer_callback_query(callback_query_id)


def download_file(file_id: str) -> Optional[str]:
    return telegram_client.download_file(file_id)
