"""
Session lifecycle management.
All writes go through the FastAPI backend (service role).
Reads for the live admin view go directly via Supabase JS (RLS).
"""
import random, string
from fastapi import APIRouter, Depends, HTTPException
from config import get_supabase_admin
from routers.auth import get_admin
from models.schemas import SessionCreate, SessionStatusUpdate, SessionStatus

router = APIRouter(prefix="/sessions", tags=["sessions"])

VALID_TRANSITIONS = {
    SessionStatus.draft:      [SessionStatus.pre_open],
    SessionStatus.pre_open:   [SessionStatus.pre_closed],
    SessionStatus.pre_closed: [SessionStatus.post_open],
    SessionStatus.post_open:  [SessionStatus.complete],
    SessionStatus.complete:   [],
}

# standalone sessions: draft → pre_open → complete (skip post phases)
STANDALONE_TRANSITIONS = {
    SessionStatus.draft:    [SessionStatus.pre_open],
    SessionStatus.pre_open: [SessionStatus.complete],
    SessionStatus.complete: [],
}


def _make_code(length=6):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def _unique_code(db):
    for _ in range(10):
        code = _make_code()
        existing = db.table("sessions").select("id").eq("short_code", code).execute()
        if not existing.data:
            return code
    raise RuntimeError("Could not generate unique short code")


@router.post("")
def create_session(body: SessionCreate, admin=Depends(get_admin)):
    db   = get_supabase_admin()
    code = _unique_code(db)

    resp = db.table("sessions").insert({
        "admin_id":   admin["id"],
        "title":      body.title.strip(),
        "short_code": code,
        "format":     body.format,
        "status":     "draft",
    }).execute()

    return resp.data[0]


@router.get("")
def list_sessions(admin=Depends(get_admin)):
    db   = get_supabase_admin()
    resp = db.table("sessions") \
             .select("*, questions(id)") \
             .eq("admin_id", admin["id"]) \
             .order("created_at", desc=True) \
             .execute()
    return resp.data


@router.get("/{session_id}")
def get_session(session_id: str, admin=Depends(get_admin)):
    db   = get_supabase_admin()
    resp = db.table("sessions") \
             .select("*, questions(*)") \
             .eq("id", session_id) \
             .eq("admin_id", admin["id"]) \
             .single() \
             .execute()
    if not resp.data:
        raise HTTPException(404, "Session not found")
    return resp.data


@router.patch("/{session_id}/status")
def update_status(session_id: str, body: SessionStatusUpdate, admin=Depends(get_admin)):
    db   = get_supabase_admin()
    sess = db.table("sessions") \
             .select("*") \
             .eq("id", session_id) \
             .eq("admin_id", admin["id"]) \
             .single() \
             .execute().data

    if not sess:
        raise HTTPException(404, "Session not found")

    current = SessionStatus(sess["status"])
    target  = body.status
    table   = STANDALONE_TRANSITIONS if sess["format"] == "standalone" else VALID_TRANSITIONS

    if target not in table.get(current, []):
        raise HTTPException(400, f"Cannot move from {current} to {target}")

    db.table("sessions").update({"status": target}).eq("id", session_id).execute()
    return {"ok": True, "status": target}


@router.delete("/{session_id}")
def delete_session(session_id: str, admin=Depends(get_admin)):
    db = get_supabase_admin()
    db.table("sessions") \
      .delete() \
      .eq("id", session_id) \
      .eq("admin_id", admin["id"]) \
      .execute()
    return {"ok": True}
