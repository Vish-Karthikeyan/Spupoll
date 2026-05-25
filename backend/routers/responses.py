"""
Participant-facing routes — no auth required.
Participants submit responses directly here; the frontend
also reads session/question data via the Supabase JS client.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from config import get_supabase_admin

router = APIRouter(prefix="/join", tags=["participant"])


class ResponseSubmit(BaseModel):
    question_id: str
    device_id:   str
    phase:       str   # "pre" or "post"
    value:       str


@router.get("/{code}")
def get_session_by_code(code: str, device_id: Optional[str] = None, phase: str = "pre"):
    """Return session + questions filtered for the requested phase. No auth."""
    db   = get_supabase_admin()
    resp = db.table("sessions") \
             .select("*, questions(*)") \
             .eq("short_code", code.upper()) \
             .neq("status", "draft") \
             .single() \
             .execute()

    if not resp.data:
        raise HTTPException(404, "Session not found or not yet open")

    sess = resp.data
    all_questions = sorted(sess.get("questions", []), key=lambda q: q["order_index"])

    # Filter to questions applicable to this phase
    def applies(q):
        ap = q.get("applicable_phase", "both")
        return ap == "both" or ap == phase

    sess["questions"] = [q for q in all_questions if applies(q)]

    # Check which phases this device has already completed
    sess["device_responded"] = {"pre": False, "post": False}
    if device_id:
        existing = db.table("responses") \
                     .select("phase, question_id") \
                     .eq("session_id", sess["id"]) \
                     .eq("device_id", device_id) \
                     .execute()
        rows = existing.data or []

        # For each phase, count how many of that phase's questions are answered
        for ph in ("pre", "post"):
            ph_questions = [q for q in all_questions if q.get("applicable_phase", "both") in ("both", ph)]
            ph_answered  = {r["question_id"] for r in rows if r["phase"] == ph}
            ph_ids       = {q["id"] for q in ph_questions}
            sess["device_responded"][ph] = bool(ph_ids) and ph_ids.issubset(ph_answered)

    return sess


@router.post("/{code}/respond")
def submit_response(code: str, body: ResponseSubmit):
    """Submit a single question response. Idempotent via upsert."""
    db = get_supabase_admin()

    # Verify the session is in the right state for this phase
    sess = db.table("sessions") \
             .select("id, status, format") \
             .eq("short_code", code.upper()) \
             .single() \
             .execute().data
    if not sess:
        raise HTTPException(404, "Session not found")

    allowed_statuses = {
        "pre":  ["pre_open"],
        "post": ["post_open"],
    }
    if sess["status"] not in allowed_statuses.get(body.phase, []):
        raise HTTPException(400, f"Session is not accepting {body.phase} responses right now")

    # Upsert — handles the case where a participant re-submits
    db.table("responses").upsert({
        "session_id":  sess["id"],
        "question_id": body.question_id,
        "device_id":   body.device_id,
        "phase":       body.phase,
        "value":       body.value,
    }, on_conflict="question_id,device_id,phase").execute()

    return {"ok": True}
