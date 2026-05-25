from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from enum import Enum


class SessionFormat(str, Enum):
    standalone = "standalone"
    pre_post   = "pre_post"


class SessionStatus(str, Enum):
    draft       = "draft"
    pre_open    = "pre_open"
    pre_closed  = "pre_closed"
    post_open   = "post_open"
    complete    = "complete"


class QuestionTemplate(str, Enum):
    scale5  = "scale5"
    likert  = "likert"
    binary  = "binary"
    mc      = "mc"
    slider  = "slider"


class Phase(str, Enum):
    pre  = "pre"
    post = "post"


# ── Sessions ──────────────────────────────────────────────────
class SessionCreate(BaseModel):
    title:  str
    format: SessionFormat


class SessionStatusUpdate(BaseModel):
    status: SessionStatus


# ── Questions ─────────────────────────────────────────────────
class QuestionCreate(BaseModel):
    template:    QuestionTemplate
    text:        str
    options:     Optional[List[str]] = None   # MC only
    anchors:     Optional[dict]      = None   # scale/slider: {lo, hi}
    order_index: int


class QuestionReorder(BaseModel):
    order: List[str]   # list of question IDs in new order


# ── Result config ─────────────────────────────────────────────
class ChartSelection(BaseModel):
    question_id: str
    charts:      List[str]


class ResultConfigSave(BaseModel):
    phase:      Phase
    selections: List[ChartSelection]


# ── Admin management ──────────────────────────────────────────
class AdminApprove(BaseModel):
    admin_id: str
