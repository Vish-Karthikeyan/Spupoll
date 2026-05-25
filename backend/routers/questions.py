from fastapi import APIRouter, Depends, HTTPException
from config import get_supabase_admin
from routers.auth import get_admin
from models.schemas import QuestionCreate, QuestionReorder

router = APIRouter(tags=["questions"])


def _assert_session_owner(db, session_id: str, admin_id: str, allow_statuses=("draft",)):
    sess = db.table("sessions") \
             .select("id, status") \
             .eq("id", session_id) \
             .eq("admin_id", admin_id) \
             .single() \
             .execute().data
    if not sess:
        raise HTTPException(404, "Session not found")
    if sess["status"] not in allow_statuses:
        raise HTTPException(400, f"Cannot modify questions in status '{sess['status']}'")
    return sess


@router.post("/sessions/{session_id}/questions")
def add_question(session_id: str, body: QuestionCreate, admin=Depends(get_admin)):
    db = get_supabase_admin()
    _assert_session_owner(db, session_id, admin["id"], allow_statuses=("draft",))

    resp = db.table("questions").insert({
        "session_id":       session_id,
        "order_index":      body.order_index,
        "template":         body.template,
        "text":             body.text.strip(),
        "options":          body.options,
        "anchors":          body.anchors,
        "applicable_phase": body.applicable_phase or "both",
    }).execute()
    return resp.data[0]


@router.post("/sessions/{session_id}/post-questions")
def set_post_questions(session_id: str, body: list, admin=Depends(get_admin)):
    """
    Called when admin chooses different post-poll questions.
    Marks all existing 'both' questions as 'pre', then inserts the new post questions.
    Only allowed when session is pre_closed.
    """
    db = get_supabase_admin()
    _assert_session_owner(db, session_id, admin["id"], allow_statuses=("pre_closed",))

    # Mark existing 'both' questions as pre-only
    db.table("questions") \
      .update({"applicable_phase": "pre"}) \
      .eq("session_id", session_id) \
      .eq("applicable_phase", "both") \
      .execute()

    # Insert new post-only questions
    for i, q in enumerate(body):
        db.table("questions").insert({
            "session_id":       session_id,
            "order_index":      i,
            "template":         q["template"],
            "text":             q["text"].strip(),
            "options":          q.get("options"),
            "anchors":          q.get("anchors"),
            "applicable_phase": "post",
        }).execute()

    return {"ok": True}


@router.patch("/sessions/{session_id}/questions/reorder")
def reorder_questions(session_id: str, body: QuestionReorder, admin=Depends(get_admin)):
    db = get_supabase_admin()
    _assert_session_owner(db, session_id, admin["id"])

    for idx, qid in enumerate(body.order):
        db.table("questions") \
          .update({"order_index": idx}) \
          .eq("id", qid) \
          .eq("session_id", session_id) \
          .execute()
    return {"ok": True}


@router.delete("/questions/{question_id}")
def delete_question(question_id: str, admin=Depends(get_admin)):
    db = get_supabase_admin()

    # Verify ownership via the session
    q = db.table("questions") \
          .select("*, sessions(admin_id, status)") \
          .eq("id", question_id) \
          .single() \
          .execute().data
    if not q:
        raise HTTPException(404, "Question not found")
    if q["sessions"]["admin_id"] != admin["id"]:
        raise HTTPException(403, "Not your session")
    if q["sessions"]["status"] != "draft":
        raise HTTPException(400, "Cannot delete questions after session is launched")

    db.table("questions").delete().eq("id", question_id).execute()
    return {"ok": True}
