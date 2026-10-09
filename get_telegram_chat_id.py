import asyncio
import httpx

from app.core.config import settings


async def main():
    token = settings.telegram_bot_token

    if not token:
        print("TELEGRAM_BOT_TOKEN is missing from .env")
        return

    url = f"https://api.telegram.org/bot{token}/getUpdates"

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

    if not data.get("ok"):
        print("Telegram API request failed.")
        return

    updates = data.get("result", [])

    for update in updates:
        message = update.get("message", {})
        chat = message.get("chat", {})

        if chat.get("id") is not None:
            print(
                f"Chat ID: {chat['id']} | "
                f"Name: {chat.get('first_name', 'Unknown')} | "
                f"Message: {message.get('text', '')}"
            )

    if not updates:
        print(
            "No updates found. Send /start to your bot and try again. "
            "If a webhook is configured, getUpdates may not work."
        )


asyncio.run(main())