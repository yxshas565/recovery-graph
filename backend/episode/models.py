# backend/episode/models.py
from enum import Enum
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class EpisodeState(str, Enum):
    CREATED            = "created"
    PROVISIONAL_FAILED = "provisional_failed"
    RETRY_PENDING      = "retry_pending"
    CAPTURED_LATE      = "captured_late"
    FINAL_FAILED       = "final_failed"
    RECOVERED          = "recovered"
    ESCALATED          = "escalated"

# State precedence — higher = wins in out-of-order delivery
STATE_PRECEDENCE = {
    EpisodeState.CREATED: 0,
    EpisodeState.PROVISIONAL_FAILED: 1,
    EpisodeState.FINAL_FAILED: 2,
    EpisodeState.RETRY_PENDING: 3,
    EpisodeState.CAPTURED_LATE: 4,
    EpisodeState.RECOVERED: 5,
    EpisodeState.ESCALATED: 5,
}

class FailureClass(str, Enum):
    INSUFFICIENT_FUNDS = "insufficient_funds"
    USER_ABANDONED     = "user_abandoned"
    BANK_DOWNTIME      = "bank_downtime"
    TIMEOUT_LATE_AUTH  = "timeout_late_auth"
    WRONG_UPI_PIN      = "wrong_upi_pin"
    LIMIT_EXCEEDED     = "limit_exceeded"
    CARD_DO_NOT_HONOR  = "card_do_not_honor"
    INVALID_VPA        = "invalid_vpa"
    EXPIRED_CARD       = "expired_card"
    THREEDS_FAILURE    = "threeds_failure"
    AMBIGUOUS          = "ambiguous"

class FailureDiagnosis(BaseModel):
    failure_class: FailureClass
    confidence: float                    # 0.0 - 1.0
    rule_hits: list[str]                 # which rules fired
    error_source: Optional[str] = None
    error_step: Optional[str] = None
    error_reason: Optional[str] = None
    is_recoverable: bool = True
    llm_used: bool = False               # True if LLM tail was invoked
    rationale: str

class RecoveryOffer(BaseModel):
    offer_type: str   # retry_same / fresh_link / capped_incentive / escalate
    amount_paise: int
    expires_in_seconds: int = 3600
    incentive_paise: int = 0
    rationale: str

class PolicyRuling(BaseModel):
    approved: bool
    selected_offer: Optional[RecoveryOffer] = None
    rejection_reason: Optional[str] = None
    rule_violations: list[str] = []

class EpisodeSnapshot(BaseModel):
    id: str
    payment_id: str
    amount_paise: int
    state: EpisodeState
    failure_class: Optional[str]
    attempts: int
    created_at: datetime
    updated_at: datetime
    recovery_link_id: Optional[str]
    intervention_type: Optional[str]