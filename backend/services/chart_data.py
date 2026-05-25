"""
Aggregates raw responses into chart-ready data structures.
Called by the results router for both in-browser rendering and PDF generation.
"""
from collections import defaultdict
from typing import List, Dict, Any


SCALE_TEMPLATES = {"scale5", "likert", "slider"}
LABEL_TEMPLATES = {"binary", "mc"}


def _ordinal_values(template: str, options=None) -> List[str]:
    if template == "scale5":
        return ["1", "2", "3", "4", "5"]
    if template == "likert":
        return ["1", "2", "3", "4", "5"]   # 1=strongly disagree … 5=strongly agree
    if template == "slider":
        return ["1", "2", "3", "4", "5"]   # binned 0-100 → 5 buckets
    if template in ("binary", "mc") and options:
        return options
    return []


def _bin_slider(value: str) -> str:
    """Map 0-100 slider value into one of 5 buckets."""
    try:
        v = float(value)
    except ValueError:
        return "3"
    bucket = min(5, max(1, int(v / 20) + 1))
    return str(bucket)


def compute_distribution(question: Dict, responses: List[Dict], phase: str) -> Dict:
    """
    Returns counts per answer option for a given phase.
    {
      "labels": ["1","2","3","4","5"],
      "counts": [3, 7, 14, 8, 2],
      "total":  34
    }
    """
    phase_responses = [r for r in responses if r["phase"] == phase]
    template = question["template"]
    options  = question.get("options") or []

    if template == "slider":
        values = [_bin_slider(r["value"]) for r in phase_responses]
        labels = ["1", "2", "3", "4", "5"]
    elif template in LABEL_TEMPLATES:
        values = [r["value"] for r in phase_responses]
        labels = options if options else sorted(set(values))
    else:
        values = [r["value"] for r in phase_responses]
        labels = ["1", "2", "3", "4", "5"]

    counts = {lbl: 0 for lbl in labels}
    for v in values:
        if v in counts:
            counts[v] += 1

    return {
        "labels": labels,
        "counts": [counts[l] for l in labels],
        "total":  len(phase_responses),
    }


def compute_sankey(question: Dict, responses: List[Dict]) -> Dict:
    """
    Returns Sankey flow data: pre → post movements.
    {
      "nodes": [{"id":"pre_1","label":"1","side":"pre"}, ...],
      "links": [{"source":"pre_1","target":"post_2","value":5,"direction":"up"}, ...]
    }
    direction: "up" (toward higher) | "down" (toward lower) | "same"
    """
    template = question["template"]
    options  = question.get("options") or []

    pre_map  = {r["device_id"]: r["value"] for r in responses if r["phase"] == "pre"}
    post_map = {r["device_id"]: r["value"] for r in responses if r["phase"] == "post"}

    if template == "slider":
        pre_map  = {k: _bin_slider(v) for k, v in pre_map.items()}
        post_map = {k: _bin_slider(v) for k, v in post_map.items()}

    labels = options if template in LABEL_TEMPLATES else ["1", "2", "3", "4", "5"]

    nodes = (
        [{"id": f"pre_{l}",  "label": l, "side": "pre"}  for l in labels] +
        [{"id": f"post_{l}", "label": l, "side": "post"} for l in labels]
    )

    flows: Dict[tuple, int] = defaultdict(int)
    for device_id, pre_val in pre_map.items():
        if device_id in post_map:
            flows[(pre_val, post_map[device_id])] += 1

    # Determine ordinal direction for coloring
    try:
        label_order = {lbl: i for i, lbl in enumerate(labels)}
        def direction(src, tgt):
            si, ti = label_order.get(src, 0), label_order.get(tgt, 0)
            if ti > si: return "up"
            if ti < si: return "down"
            return "same"
    except Exception:
        def direction(src, tgt): return "same"

    links = [
        {
            "source":    f"pre_{src}",
            "target":    f"post_{tgt}",
            "value":     count,
            "direction": direction(src, tgt),
        }
        for (src, tgt), count in flows.items() if count > 0
    ]

    return {"nodes": nodes, "links": links}


def compute_net_shift(question: Dict, responses: List[Dict]) -> Dict:
    """
    Mean before/after and percentage who changed. Ordinal questions only.
    """
    def mean_values(phase):
        vals = []
        for r in responses:
            if r["phase"] != phase:
                continue
            try:
                v = float(_bin_slider(r["value"]) if question["template"] == "slider" else r["value"])
                vals.append(v)
            except ValueError:
                pass
        return vals

    pre_vals  = mean_values("pre")
    post_vals = mean_values("post")

    pre_mean  = sum(pre_vals)  / len(pre_vals)  if pre_vals  else 0
    post_mean = sum(post_vals) / len(post_vals) if post_vals else 0

    pre_map  = {r["device_id"]: r["value"] for r in responses if r["phase"] == "pre"}
    post_map = {r["device_id"]: r["value"] for r in responses if r["phase"] == "post"}
    paired   = [(pre_map[d], post_map[d]) for d in pre_map if d in post_map]
    changed  = sum(1 for a, b in paired if a != b)

    return {
        "pre_mean":       round(pre_mean, 2),
        "post_mean":      round(post_mean, 2),
        "shift":          round(post_mean - pre_mean, 2),
        "changed_count":  changed,
        "paired_count":   len(paired),
        "changed_pct":    round(changed / len(paired) * 100, 1) if paired else 0,
    }


def compute_all(questions: List[Dict], responses: List[Dict], selections: List[Dict]) -> List[Dict]:
    """
    Main entry point: returns a list of slide data objects in the order
    matching the admin's chart selections.
    """
    resp_by_q = defaultdict(list)
    for r in responses:
        resp_by_q[r["question_id"]].append(r)

    slides = []
    for sel in selections:
        qid     = sel["question_id"]
        charts  = sel.get("charts", [])
        question = next((q for q in questions if q["id"] == qid), None)
        if not question:
            continue

        qresps = resp_by_q[qid]

        for chart in charts:
            slide = {"question_id": qid, "chart": chart, "question_text": question["text"]}

            if chart == "distribution":
                slide["pre"]  = compute_distribution(question, qresps, "pre")
                slide["post"] = compute_distribution(question, qresps, "post") if any(r["phase"] == "post" for r in qresps) else None

            elif chart == "sankey":
                slide["data"] = compute_sankey(question, qresps)

            elif chart == "net_shift":
                slide["data"] = compute_net_shift(question, qresps)

            elif chart == "pie":
                slide["pre"]  = compute_distribution(question, qresps, "pre")
                slide["post"] = compute_distribution(question, qresps, "post") if any(r["phase"] == "post" for r in qresps) else None

            slides.append(slide)

    return slides
