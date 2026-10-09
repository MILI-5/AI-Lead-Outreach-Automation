
import httpx
from app.core.config import settings

url = (
    f"https://api.telegram.org/"
    f"bot{settings.telegram_bot_token}/getWebhookInfo"
)

try:
    response = httpx.get(url, timeout=20)
    data = response.json()

    if data.get("ok"):
        result = data["result"]
        print("Webhook URL:", result.get("url") or "(none)")
        print("Pending updates:", result.get("pending_update_count", 0))
        print("Last error:", result.get("last_error_message") or "(none)")
    else:
        print("Telegram API error:", data.get("description"))

except Exception as exc:
    print("Request failed:", str(exc))