# backend/eval/synthetic_data.py
import random
import uuid
from datetime import datetime, timezone, timedelta

FAILURE_CLASSES = [
    {"class": "insufficient_funds", "share": 0.28, "naive_rate": 0.10, "agent_lift": 0.05,
     "method": "upi", "error_code": "BAD_REQUEST_ERROR",
     "error_description": "insufficient balance in account",
     "error_source": "customer", "error_step": "payment_authorization",
     "error_reason": "insufficient_funds"},
    {"class": "user_abandoned", "share": 0.14, "naive_rate": 0.20, "agent_lift": 0.06,
     "method": "upi", "error_code": "BAD_REQUEST_ERROR",
     "error_description": "payment cancelled by user",
     "error_source": "customer", "error_step": "payment_authentication",
     "error_reason": "payment_cancelled"},
    {"class": "bank_downtime", "share": 0.12, "naive_rate": 0.35, "agent_lift": 0.14,
     "method": "netbanking", "error_code": "GATEWAY_ERROR",
     "error_description": "bank server temporarily unavailable",
     "error_source": "bank", "error_step": "payment_authorization",
     "error_reason": "bank_offline"},
    {"class": "timeout_late_auth", "share": 0.12, "naive_rate": 0.30, "agent_lift": 0.10,
     "method": "upi", "error_code": "GATEWAY_ERROR",
     "error_description": "payment timed out",
     "error_source": "bank", "error_step": "payment_authorization",
     "error_reason": "payment_timed_out"},
    {"class": "wrong_upi_pin", "share": 0.10, "naive_rate": 0.15, "agent_lift": 0.04,
     "method": "upi", "error_code": "BAD_REQUEST_ERROR",
     "error_description": "wrong UPI PIN entered",
     "error_source": "customer", "error_step": "payment_authentication",
     "error_reason": "wrong_pin"},
    {"class": "limit_exceeded", "share": 0.08, "naive_rate": 0.18, "agent_lift": 0.07,
     "method": "upi", "error_code": "BAD_REQUEST_ERROR",
     "error_description": "daily transaction limit exceeded",
     "error_source": "customer", "error_step": "payment_authorization",
     "error_reason": "limit_exceeded"},
    {"class": "card_do_not_honor", "share": 0.06, "naive_rate": 0.10, "agent_lift": 0.04,
     "method": "card", "error_code": "BAD_REQUEST_ERROR",
     "error_description": "card do not honor",
     "error_source": "issuer", "error_step": "payment_authorization",
     "error_reason": "do_not_honour"},
    {"class": "invalid_vpa", "share": 0.05, "naive_rate": 0.02, "agent_lift": 0.00,
     "method": "upi", "error_code": "BAD_REQUEST_ERROR",
     "error_description": "invalid VPA provided",
     "error_source": "customer", "error_step": "payment_authentication",
     "error_reason": "invalid_vpa"},
    {"class": "expired_card", "share": 0.03, "naive_rate": 0.05, "agent_lift": 0.03,
     "method": "card", "error_code": "BAD_REQUEST_ERROR",
     "error_description": "card expired",
     "error_source": "issuer", "error_step": "payment_authorization",
     "error_reason": "expired_card"},
    {"class": "threeds_failure", "share": 0.02, "naive_rate": 0.12, "agent_lift": 0.05,
     "method": "card", "error_code": "BAD_REQUEST_ERROR",
     "error_description": "3d secure authentication failed",
     "error_source": "issuer", "error_step": "payment_authentication",
     "error_reason": "3ds_failure"},
]

def lognormal_amount(seed: int | None = None) -> int:
    rng = random.Random(seed)
    import math
    mu, sigma = math.log(400 * 100), 0.8
    raw = int(rng.lognormvariate(mu, sigma))
    return max(1000, min(raw, 10_000_000))

def generate_dataset(n: int = 200, seed: int = 42) -> list[dict]:
    rng  = random.Random(seed)
    rows = []
    now  = datetime.now(timezone.utc)

    weights = [f["share"] for f in FAILURE_CLASSES]
    for i in range(n):
        fc       = rng.choices(FAILURE_CLASSES, weights=weights, k=1)[0]
        pay_id   = f"pay_{uuid.UUID(int=rng.getrandbits(128)).hex[:14]}"
        ep_id    = f"episode:{pay_id}"
        amount   = lognormal_amount(seed + i)
        is_sub   = rng.random() < 0.25
        t_rct    = rng.random() < 0.5
        treated  = rng.random() < (0.7 if t_rct else 0.4)

        naive_p  = fc["naive_rate"]
        agent_p  = fc["naive_rate"] + fc["agent_lift"]

        if fc["class"] == "invalid_vpa":
            y0 = y1 = False
        else:
            y0 = rng.random() < naive_p
            y1 = rng.random() < agent_p

        y_obs = y1 if treated else y0

        created = now - timedelta(
            hours=rng.uniform(0, 72),
            minutes=rng.uniform(0, 60),
        )

        rows.append({
            "attempt_id":            pay_id,
            "episode_id":            ep_id,
            "failure_class":         fc["class"],
            "method":                fc["method"],
            "issuer_bank":           rng.choice(["SBI","HDFC","ICICI","AXIS","BOB","PNB"]),
            "psp":                   rng.choice(["google_pay","phonepe","paytm","bhim"]) if fc["method"] == "upi" else None,
            "amount_paise":          amount,
            "is_subscription":       is_sub,
            "prior_successes_30d":   rng.randint(0, 10),
            "prior_failures_30d":    rng.randint(0, 5),
            "prior_recovery_rate":   round(rng.uniform(0, 1), 2),
            "t_rct":                 t_rct,
            "t_obs":                 treated,
            "y0":                    y0,
            "y1":                    y1,
            "y_rct":                 y_obs if t_rct else None,
            "y_obs":                 y_obs,
            "recovered_at":          (created + timedelta(hours=rng.uniform(0.1, 6))).isoformat() if y_obs else None,
            "time_to_recovery_min":  round(rng.uniform(5, 360), 1) if y_obs else None,
            "error_code":            fc["error_code"],
            "error_description":     fc["error_description"],
            "error_source":          fc["error_source"],
            "error_step":            fc["error_step"],
            "error_reason":          fc["error_reason"],
            "created_at":            created.isoformat(),
        })

    return rows

if __name__ == "__main__":
    import json
    ds = generate_dataset(200)
    print(f"Generated {len(ds)} rows")
    print(json.dumps(ds[:2], indent=2, default=str))