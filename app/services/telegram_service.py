
import httpx

from app.core.config import settings


class TelegramService:
    def __init__(self):
        self.token = settings.telegram_bot_token

        if not self.token:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN is missing from your .env file."
            )

        self.base_url = f"https://api.telegram.org/bot{self.token}"

    async def send_message(self, chat_id: str, message: str):
        url = f"{self.base_url}/sendMessage"

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": message,
                },
            )

        response.raise_for_status()
        result = response.json()

        if not result.get("ok"):
            raise RuntimeError(
                result.get("description", "Telegram message failed.")
            )

        return result["result"]