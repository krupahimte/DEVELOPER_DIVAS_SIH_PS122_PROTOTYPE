"""Four-number gate + match_margin (spec §4.6). Never averages the four scores.

AUTO      extraction ≥ .85 AND match ≥ .85 AND date ≥ .80 AND verification ≥ .70 (.85 for finish)
          AND margin ≥ .10 AND no contradiction
CLARIFY   exactly one dimension borderline (within .15 of its threshold) with a clear margin,
          OR margin < .10 with top-2 both ≥ .70 and every other dimension passing
          (match itself may be borderline — a thin margin and a middling match are one problem)
REVIEW    anything else with a candidate ≥ .50
UNPLANNED no candidate ≥ .50
"""


def thresholds(settings: dict, finish: bool) -> dict:
    g = settings["gate"]
    return {"extraction": g["extraction"], "match": g["match"], "date": g["date"],
            "verification": g["verification_finish"] if finish else g["verification"]}


def route(scores: dict, margin: float | None, top: list, contradictions: list, settings: dict,
          finish: bool, clarify_allowed: bool) -> dict:
    """scores = {extraction, match, date, verification}. → {state, reason, dimension, failing}"""
    g = settings["gate"]
    thr = thresholds(settings, finish)
    if not top or top[0]["score"] < g["candidate_min"]:
        return {"state": "unplanned", "reason": f"no candidate ≥ {g['candidate_min']:.2f}", "dimension": None, "failing": []}
    failing = [d for d in ("extraction", "match", "date", "verification") if (scores.get(d) or 0) < thr[d]]
    borderline = [d for d in failing if thr[d] - (scores.get(d) or 0) <= g["borderline_band"]]
    margin_ok = margin is None or len(top) < 2 or margin >= g["margin"]
    if contradictions:
        return {"state": "review", "reason": "contradiction: " + "; ".join(contradictions), "dimension": None, "failing": failing}
    if not failing and margin_ok:
        return {"state": "linked", "reason": "all four scores above threshold and margin wide", "dimension": None, "failing": []}
    top2_strong = len(top) >= 2 and top[0]["score"] >= g["clarify_top2_min"] and top[1]["score"] >= g["clarify_top2_min"]
    want = None
    # a small margin *is* a match problem, so a borderline match score does not block the question
    if not margin_ok and top2_strong and set(failing) <= ({"match"} & set(borderline)):
        want = "margin"
    elif margin_ok and len(failing) == 1 and borderline:
        want = failing[0]
    if want:
        if clarify_allowed:
            return {"state": "clarifying", "reason": f"borderline {want}: asking the reporter one question", "dimension": want, "failing": failing}
        return {"state": "review", "reason": f"borderline {want} but clarification cap reached", "dimension": want, "failing": failing}
    why = []
    if failing:
        why.append("below threshold: " + ", ".join(f"{d} {scores.get(d) or 0:.2f}<{thr[d]:.2f}" for d in failing))
    if not margin_ok:
        why.append(f"margin {margin:.2f} < {g['margin']:.2f}")
    return {"state": "review", "reason": "; ".join(why), "dimension": None, "failing": failing}
