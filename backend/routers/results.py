from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from config import get_supabase_admin
from routers.auth import get_admin
from models.schemas import ResultConfigSave
from services import chart_data, pdf_generator, csv_exporter

router = APIRouter(tags=["results"])


def _load_session(db, session_id: str, admin_id: str):
    sess = db.table("sessions") \
             .select("*, questions(*)") \
             .eq("id", session_id) \
             .eq("admin_id", admin_id) \
             .single() \
             .execute().data
    if not sess:
        raise HTTPException(404, "Session not found")
    sess["questions"] = sorted(sess.get("questions", []), key=lambda q: q["order_index"])
    return sess


@router.post("/sessions/{session_id}/results/config")
def save_config(session_id: str, body: ResultConfigSave, admin=Depends(get_admin)):
    db = get_supabase_admin()
    _load_session(db, session_id, admin["id"])

    db.table("result_configs").upsert({
        "session_id": session_id,
        "admin_id":   admin["id"],
        "phase":      body.phase,
        "selections": [s.dict() for s in body.selections],
    }, on_conflict="session_id,admin_id,phase").execute()

    return {"ok": True}


@router.get("/sessions/{session_id}/results/config")
def get_config(session_id: str, phase: str, admin=Depends(get_admin)):
    db   = get_supabase_admin()
    resp = db.table("result_configs") \
             .select("*") \
             .eq("session_id", session_id) \
             .eq("admin_id", admin["id"]) \
             .eq("phase", phase) \
             .execute()
    return resp.data[0] if resp.data else {}


@router.get("/sessions/{session_id}/results/data")
def get_chart_data(session_id: str, phase: str, admin=Depends(get_admin)):
    db   = get_supabase_admin()
    sess = _load_session(db, session_id, admin["id"])

    responses = db.table("responses") \
                  .select("*") \
                  .eq("session_id", session_id) \
                  .execute().data

    config = db.table("result_configs") \
               .select("*") \
               .eq("session_id", session_id) \
               .eq("admin_id", admin["id"]) \
               .eq("phase", phase) \
               .execute().data

    if not config:
        raise HTTPException(400, "No result config saved for this phase. Use the composer first.")

    selections = config[0]["selections"]
    slides     = chart_data.compute_all(sess["questions"], responses, selections)
    return {"slides": slides}


@router.post("/sessions/{session_id}/results/pdf")
def export_pdf(session_id: str, phase: str, admin=Depends(get_admin)):
    db   = get_supabase_admin()
    sess = _load_session(db, session_id, admin["id"])

    responses = db.table("responses") \
                  .select("*") \
                  .eq("session_id", session_id) \
                  .execute().data

    config = db.table("result_configs") \
               .select("*") \
               .eq("session_id", session_id) \
               .eq("admin_id", admin["id"]) \
               .eq("phase", phase) \
               .execute().data

    if not config:
        raise HTTPException(400, "No result config saved. Use the composer first.")

    selections = config[0]["selections"]
    slides     = chart_data.compute_all(sess["questions"], responses, selections)
    pdf_bytes  = pdf_generator.generate_pdf(sess, slides)

    filename = f"spupoll_{sess['short_code']}_{phase}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/sessions/{session_id}/results/csv")
def export_csv(session_id: str, admin=Depends(get_admin)):
    db   = get_supabase_admin()
    sess = _load_session(db, session_id, admin["id"])

    responses = db.table("responses") \
                  .select("*") \
                  .eq("session_id", session_id) \
                  .execute().data

    csv_bytes = csv_exporter.generate_csv(sess, sess["questions"], responses)
    filename  = f"spupoll_{sess['short_code']}_data.csv"
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
