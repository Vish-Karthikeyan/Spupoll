"""
Exports responses to CSV. Each row is one device × question × phase.
The device_id column enables longitudinal tracking across sessions.
"""
import io, csv
from typing import List, Dict


def generate_csv(session: Dict, questions: List[Dict], responses: List[Dict]) -> bytes:
    buf    = io.StringIO()
    writer = csv.writer(buf)

    # Header
    writer.writerow([
        "session_id",
        "session_title",
        "short_code",
        "question_order",
        "question_text",
        "template",
        "device_id",
        "phase",
        "value",
        "submitted_at",
    ])

    q_map = {q["id"]: q for q in questions}

    for r in sorted(responses, key=lambda x: (x["device_id"], x["submitted_at"])):
        q = q_map.get(r["question_id"], {})
        writer.writerow([
            session["id"],
            session["title"],
            session["short_code"],
            q.get("order_index", ""),
            q.get("text", ""),
            q.get("template", ""),
            r["device_id"],
            r["phase"],
            r["value"],
            r["submitted_at"],
        ])

    return buf.getvalue().encode("utf-8")
