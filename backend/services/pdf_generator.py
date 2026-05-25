"""
Generates a multi-page PDF from computed slide data.
Uses ReportLab for layout and Plotly+Kaleido for chart images.
"""
import io, tempfile, os
from typing import List, Dict, Any

from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

import plotly.graph_objects as go

# ── SPU brand colours ──────────────────────────────────────────
SPU_RED    = colors.HexColor("#8C1515")
SPU_DARK   = colors.HexColor("#820000")
SPU_LIGHT  = colors.HexColor("#B83A4B")
SPU_GREY   = colors.HexColor("#53565A")
SPU_PURPLE = colors.HexColor("#534AB7")
PAGE_W, PAGE_H = landscape(A4)
MARGIN = 2 * cm


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=20,
                                textColor=SPU_RED, spaceAfter=6, alignment=TA_CENTER),
        "subtitle": ParagraphStyle("subtitle", fontName="Helvetica", fontSize=12,
                                   textColor=SPU_GREY, spaceAfter=12, alignment=TA_CENTER),
        "qtext": ParagraphStyle("qtext", fontName="Helvetica-Bold", fontSize=13,
                                textColor=colors.HexColor("#2E2D29"), spaceAfter=8),
        "label": ParagraphStyle("label", fontName="Helvetica", fontSize=9,
                                textColor=SPU_GREY),
        "stat_big": ParagraphStyle("stat_big", fontName="Helvetica-Bold", fontSize=28,
                                   textColor=SPU_RED, alignment=TA_CENTER),
        "stat_label": ParagraphStyle("stat_label", fontName="Helvetica", fontSize=10,
                                     textColor=SPU_GREY, alignment=TA_CENTER),
    }


# ── Chart image helpers ────────────────────────────────────────

def _bar_image(dist_pre: Dict, dist_post: Dict | None, width=480, height=260) -> bytes:
    labels = dist_pre["labels"]
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name="Before",
        x=labels,
        y=dist_pre["counts"],
        marker_color=SPU_RED.hexval().replace("0x", "#"),
        opacity=0.55,
    ))
    if dist_post:
        fig.add_trace(go.Bar(
            name="After",
            x=labels,
            y=dist_post["counts"],
            marker_color=SPU_RED.hexval().replace("0x", "#"),
            opacity=0.9,
        ))

    fig.update_layout(
        barmode="group",
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Helvetica", size=11),
        margin=dict(l=30, r=30, t=20, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        width=width, height=height,
    )
    return fig.to_image(format="png")


def _sankey_image(data: Dict, width=560, height=300) -> bytes:
    nodes = data["nodes"]
    links = data["links"]

    node_labels = [n["label"] for n in nodes]
    node_ids    = {n["id"]: i for i, n in enumerate(nodes)}

    link_colors = []
    for lnk in links:
        if lnk["direction"] == "up":
            link_colors.append("rgba(140,21,21,0.35)")
        elif lnk["direction"] == "down":
            link_colors.append("rgba(83,74,183,0.35)")
        else:
            link_colors.append("rgba(83,83,83,0.2)")

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            label=node_labels,
            color=["rgba(140,21,21,0.75)"] * len(nodes),
            pad=12, thickness=16,
        ),
        link=dict(
            source=[node_ids[l["source"]] for l in links],
            target=[node_ids[l["target"]] for l in links],
            value=[l["value"] for l in links],
            color=link_colors,
        ),
    ))
    fig.update_layout(
        paper_bgcolor="white",
        font=dict(family="Helvetica", size=10),
        margin=dict(l=20, r=20, t=20, b=20),
        width=width, height=height,
    )
    return fig.to_image(format="png")


def _pie_image(dist_pre: Dict, dist_post: Dict | None, width=480, height=260) -> bytes:
    cols = 2 if dist_post else 1
    from plotly.subplots import make_subplots
    fig = make_subplots(rows=1, cols=cols, specs=[[{"type": "pie"}] * cols])

    reds = ["#8C1515", "#B83A4B", "#D47A7A", "#E8ACAC", "#F5D5D5"]

    fig.add_trace(go.Pie(
        labels=dist_pre["labels"],
        values=dist_pre["counts"],
        name="Before",
        marker_colors=reds[:len(dist_pre["labels"])],
        title="Before",
    ), row=1, col=1)

    if dist_post:
        fig.add_trace(go.Pie(
            labels=dist_post["labels"],
            values=dist_post["counts"],
            name="After",
            marker_colors=reds[:len(dist_post["labels"])],
            title="After",
        ), row=1, col=2)

    fig.update_layout(
        paper_bgcolor="white",
        font=dict(family="Helvetica", size=10),
        margin=dict(l=20, r=20, t=30, b=20),
        width=width, height=height,
    )
    return fig.to_image(format="png")


# ── Cover page ────────────────────────────────────────────────

def _cover(session: Dict, styles: Dict, elements: list):
    elements.append(Spacer(1, 3 * cm))
    elements.append(Paragraph("Spupoll™", styles["title"]))
    elements.append(Paragraph("Stanford Political Union", styles["subtitle"]))
    elements.append(Spacer(1, 0.5 * cm))
    elements.append(Paragraph(session["title"], ParagraphStyle(
        "cover_title", fontName="Helvetica-Bold", fontSize=22,
        textColor=colors.HexColor("#2E2D29"), alignment=TA_CENTER, spaceAfter=6
    )))
    from datetime import datetime
    date_str = datetime.utcnow().strftime("%-d %B %Y")
    elements.append(Paragraph(date_str, styles["subtitle"]))
    elements.append(PageBreak())


# ── Main generator ────────────────────────────────────────────

def generate_pdf(session: Dict, slides: List[Dict]) -> bytes:
    buf    = io.BytesIO()
    doc    = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
    )
    styles   = _styles()
    elements = []

    _cover(session, styles, elements)

    for slide in slides:
        elements.append(Paragraph(slide["question_text"], styles["qtext"]))
        elements.append(Spacer(1, 0.3 * cm))

        chart = slide["chart"]
        img_bytes = None

        if chart == "distribution":
            img_bytes = _bar_image(slide["pre"], slide.get("post"))

        elif chart == "sankey":
            img_bytes = _sankey_image(slide["data"])

        elif chart == "net_shift":
            d = slide["data"]
            data_table = [
                ["", "Before", "After", "Shift", "Changed"],
                [
                    "",
                    f"{d['pre_mean']:.1f}",
                    f"{d['post_mean']:.1f}",
                    ("+" if d["shift"] >= 0 else "") + f"{d['shift']:.1f}",
                    f"{d['changed_pct']:.0f}% ({d['changed_count']} of {d['paired_count']})",
                ],
            ]
            t = Table(data_table, colWidths=[3*cm, 3*cm, 3*cm, 3*cm, 6*cm])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), SPU_RED),
                ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
                ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE",   (0, 0), (-1, -1), 11),
                ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
                ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ]))
            elements.append(t)
            elements.append(PageBreak())
            continue

        elif chart == "pie":
            img_bytes = _pie_image(slide["pre"], slide.get("post"))

        if img_bytes:
            elements.append(Image(io.BytesIO(img_bytes),
                                  width=PAGE_W - 2 * MARGIN,
                                  height=8 * cm,
                                  kind="proportional"))

        elements.append(PageBreak())

    doc.build(elements)
    return buf.getvalue()
