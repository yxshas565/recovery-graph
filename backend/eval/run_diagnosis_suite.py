# backend/eval/run_diagnosis_suite.py
"""
Seeded diagnosis precision/recall test suite.
Run: python -m eval.run_diagnosis_suite
"""
import asyncio
import os
from agents.diagnosis import rules_classify
from eval.synthetic_data import generate_dataset, FAILURE_CLASSES

async def run_suite(n: int = 200, seed: int = 42):
    rows = generate_dataset(n, seed)

    tp = fp = tn = fn = 0
    misses = []

    for row in rows:
        predicted, hits, confidence = rules_classify(
            error_code=row["error_code"],
            error_description=row["error_description"],
            error_source=row["error_source"],
            error_step=row["error_step"],
            error_reason=row["error_reason"],
            method=row["method"],
            has_active_downtime=(row["failure_class"] == "bank_downtime"),
        )

        actual = row["failure_class"]
        pred   = predicted.value if predicted else "ambiguous"

        if pred == actual:
            tp += 1
        else:
            fp += 1
            misses.append({
                "actual": actual, "predicted": pred,
                "confidence": round(confidence, 2),
                "hits": hits,
                "error_desc": row["error_description"],
            })

    total     = len(rows)
    precision = tp / max(tp + fp, 1)
    recall    = tp / max(tp + fn + total - tp - fp, 1)

    print(f"\n{'─'*50}")
    print(f"  Diagnosis Suite Results (n={total})")
    print(f"{'─'*50}")
    print(f"  Correct   : {tp}/{total} ({tp/total*100:.1f}%)")
    print(f"  Precision : {precision:.3f}")
    print(f"  Recall    : {recall:.3f}")
    print(f"\n  Misclassified ({len(misses)}):")
    for m in misses[:10]:
        print(f"    actual={m['actual']:25s} pred={m['predicted']:25s} "
              f"conf={m['confidence']:.2f}")

    return {"precision": precision, "recall": recall,
            "correct": tp, "total": total, "misses": misses}

if __name__ == "__main__":
    asyncio.run(run_suite())