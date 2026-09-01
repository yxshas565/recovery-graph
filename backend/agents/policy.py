# backend/agents/policy.py
import logging
from datetime import datetime, timezone

from config import get_settings
from episode.models import (
    FailureClass, FailureDiagnosis,
    RecoveryOffer, PolicyRuling,
)

logger   = logging.getLogger(__name__)
settings = get_settings()

# Recovery offer catalog per failure class
OFFER_CATALOG: dict[FailureClass, list[dict]] = {
    FailureClass.INSUFFICIENT_FUNDS: [
        {"offer_type": "fresh_link", "expires_in_seconds": 86400,
         "incentive_paise": 0, "rationale": "Retry after payday window"},
    ],
    FailureClass.USER_ABANDONED: [
        {"offer_type": "fresh_link", "expires_in_seconds": 3600,
         "incentive_paise": 0, "rationale": "One-click recovery link"},
    ],
    FailureClass.BANK_DOWNTIME: [
        {"offer_type": "fresh_link", "expires_in_seconds": 7200,
         "incentive_paise": 0,
         "rationale": "Retry after downtime.resolved webhook"},
    ],
    FailureClass.TIMEOUT_LATE_AUTH: [
        {"offer_type": "fresh_link", "expires_in_seconds": 3600,
         "incentive_paise": 0, "rationale": "UPI timeout retry"},
    ],
    FailureClass.WRONG_UPI_PIN: [
        {"offer_type": "fresh_link", "expires_in_seconds": 86400,
         "incentive_paise": 0, "rationale": "Retry after 24h PIN lockout clears"},
    ],
    FailureClass.LIMIT_EXCEEDED: [
        {"offer_type": "fresh_link", "expires_in_seconds": 86400,
         "incentive_paise": 0, "rationale": "Retry after daily limit resets"},
    ],
    FailureClass.CARD_DO_NOT_HONOR: [
        {"offer_type": "fresh_link", "expires_in_seconds": 3600,
         "incentive_paise": 0, "rationale": "Alternate method offer"},
    ],
    FailureClass.EXPIRED_CARD: [
        {"offer_type": "fresh_link", "expires_in_seconds": 3600,
         "incentive_paise": 0, "rationale": "Card update deep-link"},
    ],
    FailureClass.THREEDS_FAILURE: [
        {"offer_type": "fresh_link", "expires_in_seconds": 3600,
         "incentive_paise": 0, "rationale": "Re-auth with step-up"},
    ],
    FailureClass.INVALID_VPA: [],       # structural — unrecoverable
    FailureClass.AMBIGUOUS: [
        {"offer_type": "escalate", "expires_in_seconds": 0,
         "incentive_paise": 0, "rationale": "Ambiguous failure — escalate"},
    ],
}

def is_quiet_hours() -> bool:
    hour = datetime.now(timezone.utc).hour
    start, end = settings.quiet_hours_start, settings.quiet_hours_end
    if start > end:
        return hour >= start or hour < end
    return start <= hour < end

def evaluate_policy(
    episode: dict,
    diagnosis: FailureDiagnosis,
) -> PolicyRuling:
    violations: list[str] = []

    # 1. Unrecoverable failure class
    if not diagnosis.is_recoverable:
        return PolicyRuling(
            approved=False,
            rejection_reason="failure_class_unrecoverable",
            rule_violations=["unrecoverable_class"],
        )

    # 2. Max attempts
    if episode.get("attempts", 0) >= settings.max_recovery_attempts:
        violations.append("max_attempts_exceeded")
        return PolicyRuling(
            approved=False,
            rejection_reason="max_recovery_attempts_exceeded",
            rule_violations=violations,
        )

    # 3. Quiet hours
    if is_quiet_hours():
        violations.append("quiet_hours")
        return PolicyRuling(
            approved=False,
            rejection_reason="quiet_hours_block",
            rule_violations=violations,
        )

    # 4. Amount cap
    amount = episode.get("amount_paise", 0)
    if amount > settings.max_recovery_amount_paise:
        violations.append("amount_exceeds_cap")
        return PolicyRuling(
            approved=False,
            rejection_reason="amount_exceeds_recovery_cap",
            rule_violations=violations,
        )

    # 5. Select offer from catalog
    offers = OFFER_CATALOG.get(diagnosis.failure_class, [])
    if not offers:
        return PolicyRuling(
            approved=False,
            rejection_reason="no_offer_available",
            rule_violations=["no_catalog_entry"],
        )

    best = offers[0]
    offer = RecoveryOffer(
        offer_type=best["offer_type"],
        amount_paise=amount,
        expires_in_seconds=best["expires_in_seconds"],
        incentive_paise=best["incentive_paise"],
        rationale=best["rationale"],
    )

    if offer.offer_type == "escalate":
        return PolicyRuling(
            approved=False,
            rejection_reason="escalated",
            rule_violations=["ambiguous_failure"],
        )

    return PolicyRuling(approved=True, selected_offer=offer)