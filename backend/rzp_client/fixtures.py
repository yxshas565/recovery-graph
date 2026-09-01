# backend/razorpay/fixtures.py
"""
Synthetic webhook payload builders for all failure scenarios.
Used by the diagnosis agent test suite.
"""
import uuid
from datetime import datetime, timezone

def make_payment_failed(
    payment_id: str | None = None,
    amount_paise: int = 50000,
    method: str = "upi",
    error_code: str = "BAD_REQUEST_ERROR",
    error_description: str = "Payment failed",
    error_source: str = "customer",
    error_step: str = "payment_authorization",
    error_reason: str = "payment_cancelled",
    vpa: str | None = "test@upi",
) -> dict:
    pid = payment_id or f"pay_{uuid.uuid4().hex[:14]}"
    return {
        "event": "payment.failed",
        "payload": {"payment": {"entity": {
            "id": pid, "entity": "payment",
            "amount": amount_paise, "currency": "INR",
            "status": "failed", "method": method,
            "error_code": error_code,
            "error_description": error_description,
            "error_source": error_source,
            "error_step": error_step,
            "error_reason": error_reason,
            "vpa": vpa,
            "created_at": int(datetime.now(timezone.utc).timestamp()),
        }}},
    }

def make_payment_captured(payment_id: str, amount_paise: int = 50000,
                           method: str = "upi") -> dict:
    return {
        "event": "payment.captured",
        "payload": {"payment": {"entity": {
            "id": payment_id, "entity": "payment",
            "amount": amount_paise, "currency": "INR",
            "status": "captured", "method": method, "captured": True,
            "created_at": int(datetime.now(timezone.utc).timestamp()),
        }}},
    }

def make_downtime_started(method: str = "upi", severity: str = "high") -> dict:
    return {
        "event": "payment.downtime.started",
        "payload": {"payment.downtime": {"entity": {
            "id": f"down_{uuid.uuid4().hex[:14]}",
            "entity": "payment.downtime",
            "method": method, "status": "started",
            "severity": severity, "scheduled": False,
            "begin": int(datetime.now(timezone.utc).timestamp()),
            "end": None,
            "created_at": int(datetime.now(timezone.utc).timestamp()),
        }}},
    }

# Full scenario sequences
SCENARIOS: dict[str, list[dict]] = {
    "upi_late_capture": [
        make_payment_failed(method="upi", error_description="payment timed out"),
        # Same pay_ id — captured after failure (documented Razorpay UPI retry)
    ],
    "card_expired": [
        make_payment_failed(method="card", error_description="card expired",
                            error_reason="expired_card", error_source="issuer",
                            vpa=None),
    ],
    "insufficient_funds": [
        make_payment_failed(error_description="insufficient balance in account",
                            error_reason="insufficient_funds"),
    ],
    "bank_downtime": [
        make_downtime_started(method="upi", severity="high"),
        make_payment_failed(method="upi", error_code="GATEWAY_ERROR",
                            error_description="bank server unavailable",
                            error_source="bank", error_reason="bank_offline"),
    ],
    "wrong_upi_pin": [
        make_payment_failed(error_description="wrong UPI PIN entered",
                            error_reason="wrong_pin"),
    ],
    "invalid_vpa": [
        make_payment_failed(error_description="invalid VPA provided",
                            error_reason="invalid_vpa"),
    ],
}