# backend/agents/diagnosis.py
import hashlib
import logging
from typing import Literal

import psycopg
from langchain_anthropic import ChatAnthropic
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain.tools import tool
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from config import get_settings
from episode.models import FailureClass, FailureDiagnosis

logger   = logging.getLogger(__name__)
settings = get_settings()

# ── PROMPT REGISTRY ──────────────────────────────────────────────────────────
DIAGNOSIS_PROMPT_V1 = """You are a payment failure diagnosis expert for Indian fintech.
You receive a structured failure context and must classify the failure type.

Rules:
- Only classify as ambiguous if NO rule matched
- Never return free text — always use the structured output tool
- is_recoverable = False ONLY for invalid_vpa and structural failures
- Confidence < 0.7 means you are uncertain — say so in rationale

Failure classes: insufficient_funds, user_abandoned, bank_downtime,
timeout_late_auth, wrong_upi_pin, limit_exceeded, card_do_not_honor,
invalid_vpa, expired_card, threeds_failure, ambiguous
"""

def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]

def register_prompt(conninfo: str) -> str:
    sha = prompt_hash(DIAGNOSIS_PROMPT_V1)
    with psycopg.connect(conninfo) as conn:
        conn.execute(
            """INSERT INTO prompt_registry(name, version, sha256, template)
               VALUES (%s,%s,%s,%s) ON CONFLICT (name, version) DO NOTHING""",
            ("diagnosis", "v1", sha, DIAGNOSIS_PROMPT_V1),
        )
        conn.commit()
    return sha

# ── RULES-FIRST CLASSIFIER ───────────────────────────────────────────────────
def rules_classify(
    error_code: str | None,
    error_description: str | None,
    error_source: str | None,
    error_step: str | None,
    error_reason: str | None,
    method: str | None,
    has_active_downtime: bool,
) -> tuple[FailureClass | None, list[str], float]:
    desc = (error_description or "").lower()
    code = (error_code or "").lower()
    src = (error_source or "").lower()
    step = (error_step or "").lower()
    rsn = (error_reason or "").lower()
    meth = (method or "").lower()
    hits: list[str] = []

    if has_active_downtime and meth in ("upi", "netbanking", "card"):
        hits.append("active_downtime_event")
        return FailureClass.BANK_DOWNTIME, hits, 0.92

    # User explicitly cancelled/abandoned the payment.
    # Check this BEFORE generic authentication/3DS detection because
    # payment_authentication is also used for normal user cancellation.
    if (
        "cancel" in desc
        or "abandon" in desc
        or "cancelled" in rsn
        or "abandoned" in rsn
    ) and (
        "user" in desc
        or "customer" in src
        or "user" in src
    ):
        hits.append("user_cancel_or_abandon")
        return FailureClass.USER_ABANDONED, hits, 0.90

    if "insufficient" in desc or "fund" in desc or "balance" in desc:
        hits.append("desc:insufficient_funds")
        return FailureClass.INSUFFICIENT_FUNDS, hits, 0.95

    if "wrong" in desc and "pin" in desc:
        hits.append("desc:wrong_upi_pin")
        return FailureClass.WRONG_UPI_PIN, hits, 0.93

    if "pin" in rsn or "wrong_pin" in rsn:
        hits.append("reason:wrong_pin")
        return FailureClass.WRONG_UPI_PIN, hits, 0.90

    if "expired" in desc or "expir" in rsn:
        hits.append("desc:expired_card")
        return FailureClass.EXPIRED_CARD, hits, 0.92

    if "invalid" in desc and ("vpa" in desc or "upi" in desc):
        hits.append("desc:invalid_vpa")
        return FailureClass.INVALID_VPA, hits, 0.95

    if "limit" in desc or "exceed" in desc or "limit_exceeded" in rsn:
        hits.append("desc:limit_exceeded")
        return FailureClass.LIMIT_EXCEEDED, hits, 0.90

    if (
        "do not honor" in desc
        or "do_not_honour" in rsn
        or "card_do_not_honor" in code
    ):
        hits.append("desc:do_not_honor")
        return FailureClass.CARD_DO_NOT_HONOR, hits, 0.88

    if (
        "3ds" in desc
        or "3d_secure" in rsn
        or "authentication" in step
    ):
        hits.append("desc:3ds_failure")
        return FailureClass.THREEDS_FAILURE, hits, 0.87

    if code == "gateway_error" and meth == "upi":
        hits.append("code:gateway_error+upi")
        return FailureClass.TIMEOUT_LATE_AUTH, hits, 0.80

    if "timeout" in desc or "timed out" in desc:
        hits.append("desc:timeout")
        return FailureClass.TIMEOUT_LATE_AUTH, hits, 0.82

    return None, [], 0.0

# ── DIAGNOSIS AGENT ──────────────────────────────────────────────────────────
async def diagnose(
    episode_id: str,
    payment_id: str,
    method: str | None,
    amount_paise: int,
    error_code: str | None,
    error_description: str | None,
    error_source: str | None,
    error_step: str | None,
    error_reason: str | None,
    has_active_downtime: bool,
    conninfo: str,
) -> FailureDiagnosis:

    # Rules first
    failure_class, rule_hits, confidence = rules_classify(
        error_code, error_description, error_source,
        error_step, error_reason, method, has_active_downtime,
    )

    if failure_class and confidence >= 0.80:
        return FailureDiagnosis(
            failure_class=failure_class,
            confidence=confidence,
            rule_hits=rule_hits,
            error_source=error_source,
            error_step=error_step,
            error_reason=error_reason,
            is_recoverable=failure_class != FailureClass.INVALID_VPA,
            llm_used=False,
            rationale=f"Rules matched: {', '.join(rule_hits)}",
        )

    # LLM tail for ambiguous cases
    logger.info("rules inconclusive for %s — invoking LLM tail", episode_id)
    sha = register_prompt(conninfo)

    llm   = ChatAnthropic(
        model="claude-sonnet-4-6",
        api_key=settings.anthropic_api_key,
    )

    class DiagnosisOutput(BaseModel):
        failure_class:  FailureClass
        confidence:     float = Field(ge=0.0, le=1.0)
        is_recoverable: bool
        rationale:      str = Field(max_length=400)

    agent  = create_agent(
        model=llm,
        tools=[],
        response_format=ToolStrategy(DiagnosisOutput, handle_errors=True),
        system_message=DIAGNOSIS_PROMPT_V1,
    )

    case_summary = (
        f"Payment {payment_id} | method={method} | amount={amount_paise} paise\n"
        f"error_code={error_code} | error_description={error_description}\n"
        f"error_source={error_source} | error_step={error_step} | error_reason={error_reason}\n"
        f"active_downtime={has_active_downtime}"
    )

    result   = agent.invoke({"messages": [{"role": "user", "content": case_summary}]})
    output: DiagnosisOutput = result["structured_response"]

    return FailureDiagnosis(
        failure_class=output.failure_class,
        confidence=output.confidence,
        rule_hits=rule_hits or ["llm_tail"],
        error_source=error_source,
        error_step=error_step,
        error_reason=error_reason,
        is_recoverable=output.is_recoverable,
        llm_used=True,
        rationale=output.rationale,
    )