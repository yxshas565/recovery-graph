# backend/razorpay/payment_links.py
import logging
import time
import razorpay
from config import get_settings
# from rzp_client.client import get_razorpay_client
from rzp_client.client import get_razorpay_client

logger   = logging.getLogger(__name__)
settings = get_settings()

def create_recovery_link(
    episode_id: str,
    amount_paise: int,
    attempt_num: int,
    contact: str | None = None,
    email:   str | None = None,
    description: str = "Payment recovery link",
    expire_in_seconds: int = 3600,
) -> dict:
    client = get_razorpay_client()

    # reference_id is our idempotency key — duplicate → 400
    reference_id = f"rcv:{episode_id}:{attempt_num}"
    # Max 40 chars — truncate episode prefix if needed
    reference_id = reference_id[:40]

    payload: dict = {
        "amount":           amount_paise,
        "currency":         "INR",
        "reference_id":     reference_id,
        "description":      description[:2048],
        "expire_by":        int(time.time()) + expire_in_seconds,
        "reminder_enable":  False,
        "notify":           {"sms": False, "email": False},
        "notes": {
            "episode_id":   episode_id,
            "attempt_num":  str(attempt_num),
            "source":       "recovery_graph",
        },
    }

    if contact or email:
        customer: dict = {}
        if contact:
            customer["contact"] = contact
        if email:
            customer["email"] = email
        payload["customer"] = customer

    try:
        link = client.payment_link.create(payload)
        logger.info(
            "created recovery link %s ref=%s ep=%s",
            link["id"], reference_id, episode_id,
        )
        return link
    except razorpay.errors.BadRequestError as e:
        # reference_id already used → idempotent return
        if "reference ID already attempted" in str(e):
            logger.warning(
                "duplicate recovery link attempt for ref=%s", reference_id
            )
            raise
        raise

def fetch_payment_link(link_id: str) -> dict:
    client = get_razorpay_client()
    return client.payment_link.fetch(link_id)
