# backend/razorpay/client.py
import logging
import razorpay
from config import get_settings

logger   = logging.getLogger(__name__)
settings = get_settings()

_client: razorpay.Client | None = None

def get_razorpay_client() -> razorpay.Client:
    global _client
    if _client is None:
        _client = razorpay.Client(
            auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
        )
    return _client

def fetch_payment(payment_id: str) -> dict:
    client = get_razorpay_client()
    return client.payment.fetch(payment_id)

def capture_payment(payment_id: str, amount_paise: int) -> dict:
    client = get_razorpay_client()
    return client.payment.capture(payment_id, amount_paise, {"currency": "INR"})

def fetch_order(order_id: str) -> dict:
    client = get_razorpay_client()
    return client.order.fetch(order_id)

def create_order(amount_paise: int, receipt: str) -> dict:
    client = get_razorpay_client()
    return client.order.create({
        "amount":   amount_paise,
        "currency": "INR",
        "receipt":  receipt,
    })

def list_downtimes() -> dict:
    client = get_razorpay_client()
    return client.payment.fetch_all({"downtimes": True})