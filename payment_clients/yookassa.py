import uuid
import json
import base64
import aiohttp
from app.logger import get_logger

logger = get_logger("yookassa")


class YooKassaClient:
    """
    YooKassa API client.
    Docs: https://yookassa.ru/developers/api
    """

    BASE_URL = "https://api.yookassa.ru/v3"

    def __init__(self, shop_id: str, secret_key: str, is_test: bool = False):
        self.shop_id = shop_id
        self.secret_key = secret_key
        self.is_test = is_test
        self._basic_auth = base64.b64encode(
            f"{shop_id}:{secret_key}".encode()
        ).decode()

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Basic {self._basic_auth}",
            "Idempotence-Key": str(uuid.uuid4()),
        }

    async def create_payment(
        self,
        amount_rub: int,
        description: str,
        return_url: str,
        metadata: dict = None,
    ) -> dict:
        """Create a YooKassa payment and return the response dict."""
        payload = {
            "amount": {
                "value": f"{amount_rub:.2f}",
                "currency": "RUB",
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url,
            },
            "capture": True,
            "description": description,
            "test": self.is_test,
        }
        if metadata:
            payload["metadata"] = metadata

        url = f"{self.BASE_URL}/payments"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self._headers(), json=payload) as resp:
                data = await resp.json()
                if resp.status != 200:
                    logger.error(f"YooKassa create payment error: {resp.status} {data}")
                    raise Exception(f"YooKassa API error {resp.status}: {data.get('description', data)}")
                logger.info(f"YooKassa payment created: {data.get('id')}")
                return data

    def verify_webhook_signature(self, payload_body: str, signature: str) -> bool:
        """Verify YooKassa webhook signature (HMAC-SHA256 with secret_key)."""
        import hmac
        import hashlib
        expected = hmac.new(
            self.secret_key.encode(),
            payload_body.encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
