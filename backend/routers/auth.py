"""
Admin authentication and account management.

- Any Supabase-authenticated user can call /me.
- Only approved admins can call the admin-protected routes.
- Only super admins (is_super=true) can approve / revoke other admins.
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional
from config import get_supabase_admin, get_settings
from models.schemas import AdminApprove

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Shared dependency ──────────────────────────────────────────

def get_admin(authorization: Optional[str] = Header(None)):
    """Verify Bearer token and return the admins row."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1]
    db    = get_supabase_admin()

    try:
        user_resp = db.auth.get_user(token)
        user      = user_resp.user
    except Exception:
        raise HTTPException(401, "Invalid or expired token")

    admin_resp = db.table("admins").select("*").eq("id", str(user.id)).single().execute()
    admin      = admin_resp.data

    if not admin:
        raise HTTPException(403, "Admin record not found")
    if not admin["approved"]:
        raise HTTPException(403, "Account pending approval")

    return admin


def get_super_admin(admin=Depends(get_admin)):
    if not admin.get("is_super"):
        raise HTTPException(403, "Super-admin access required")
    return admin


# ── Routes ────────────────────────────────────────────────────

@router.get("/me")
def me(authorization: Optional[str] = Header(None)):
    """Return the current admin's profile (approved or not)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")

    token = authorization.split(" ", 1)[1]
    db    = get_supabase_admin()

    try:
        user = db.auth.get_user(token).user
    except Exception:
        raise HTTPException(401, "Invalid token")

    resp  = db.table("admins").select("*").eq("id", str(user.id)).single().execute()
    if not resp.data:
        raise HTTPException(404, "Admin not found")

    return resp.data


@router.get("/pending")
def list_pending(admin=Depends(get_super_admin)):
    """List admins awaiting approval."""
    db   = get_supabase_admin()
    resp = db.table("admins").select("*").eq("approved", False).execute()
    return resp.data


@router.get("/admins")
def list_all_admins(admin=Depends(get_super_admin)):
    """List all admin accounts."""
    db   = get_supabase_admin()
    resp = db.table("admins").select("*").order("created_at").execute()
    return resp.data


@router.post("/approve")
def approve_admin(body: AdminApprove, super_admin=Depends(get_super_admin)):
    """Approve a pending admin account."""
    db = get_supabase_admin()
    db.table("admins").update({
        "approved":    True,
        "approved_by": super_admin["id"],
    }).eq("id", body.admin_id).execute()
    return {"ok": True}


@router.post("/revoke")
def revoke_admin(body: AdminApprove, super_admin=Depends(get_super_admin)):
    """Revoke an admin's access (sets approved=false, is_super unchanged)."""
    if body.admin_id == super_admin["id"]:
        raise HTTPException(400, "Cannot revoke yourself")
    db = get_supabase_admin()
    db.table("admins").update({"approved": False}).eq("id", body.admin_id).execute()
    return {"ok": True}
