# backend/agents/graph.py
import logging
from typing import TypedDict, Annotated, Literal
from langchain_core.runnables import RunnableConfig
import operator

from langgraph.graph import StateGraph, START, END
# from langgraph.types import Command

from config import get_settings
from episode.models import FailureDiagnosis, PolicyRuling
from agents.diagnosis import diagnose
from agents.policy import evaluate_policy
from agents.executor import execute_recovery
from ledger.audit_ledger import AuditLedger

logger   = logging.getLogger(__name__)
settings = get_settings()

class EpisodeAgentState(TypedDict, total=False):
    episode_id:          str
    payment_id:          str
    amount_paise:        int
    method:              str | None
    error_code:          str | None
    error_description:   str | None
    error_source:        str | None
    error_step:          str | None
    error_reason:        str | None
    has_active_downtime: bool
    diagnosis:           dict | None
    ruling:              dict | None
    result:              dict | None
    events: Annotated[list[dict], operator.add]

async def diagnosis_node(state: EpisodeAgentState, config: RunnableConfig) -> dict:
    conn = config["configurable"]["conn"]
    conninfo = config["configurable"]["conninfo"]

    diagnosis = await diagnose(
        episode_id=state["episode_id"],
        payment_id=state["payment_id"],
        method=state.get("method"),
        amount_paise=state["amount_paise"],
        error_code=state.get("error_code"),
        error_description=state.get("error_description"),
        error_source=state.get("error_source"),
        error_step=state.get("error_step"),
        error_reason=state.get("error_reason"),
        has_active_downtime=state.get("has_active_downtime", False),
        conninfo=conninfo,
    )

    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE episodes SET failure_class = %s, updated_at = NOW() WHERE id = %s",
            (diagnosis.failure_class.value, state["episode_id"]),
        )
        await conn.commit()

    logger.info(
        "diagnosed episode=%s class=%s confidence=%.2f llm_used=%s",
        state["episode_id"],
        diagnosis.failure_class,
        diagnosis.confidence,
        diagnosis.llm_used,
    )

    return {
        "diagnosis": diagnosis.model_dump(),
        "events": [
            {
                "type": "diagnosed",
                "class": diagnosis.failure_class.value,
                "confidence": diagnosis.confidence,
                "llm_used": diagnosis.llm_used,
            }
        ],
    }
async def policy_node(state: EpisodeAgentState, config: RunnableConfig) -> dict:
    episode   = config["configurable"]["episode"]
    diagnosis = FailureDiagnosis(**state["diagnosis"])
    ruling    = evaluate_policy(episode, diagnosis)
    return {
        "ruling": ruling.model_dump(),
        "events": [{"type": "policy_evaluated", "approved": ruling.approved}],
    }

async def executor_node(state: EpisodeAgentState, config: RunnableConfig) -> dict:
    conn    = config["configurable"]["conn"]
    episode = config["configurable"]["episode"]
    ledger  = config["configurable"]["ledger"]

    diagnosis = FailureDiagnosis(**state["diagnosis"])
    ruling    = PolicyRuling(**state["ruling"])

    result = await execute_recovery(
        conn=conn,
        episode=episode,
        ruling=ruling,
        diagnosis_payload=state["diagnosis"],
        ledger=ledger,
    )
    return {
        "result": result,
        "events": [{"type": "executed", "action": result.get("action")}],
    }

def route_after_policy(state: EpisodeAgentState) -> Literal["executor", END]:
    ruling = state.get("ruling", {})
    if ruling.get("approved"):
        return "executor"
    return END

def build_recovery_graph():
    builder = StateGraph(EpisodeAgentState)
    builder.add_node("diagnosis", diagnosis_node)
    builder.add_node("policy",    policy_node)
    builder.add_node("executor",  executor_node)
    builder.add_edge(START, "diagnosis")
    builder.add_edge("diagnosis", "policy")
    builder.add_conditional_edges("policy", route_after_policy,
                                  {"executor": "executor", END: END})
    builder.add_edge("executor", END)
    return builder.compile()

recovery_graph = build_recovery_graph()

