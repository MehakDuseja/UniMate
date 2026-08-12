"""Aggregate university stats for the Analytics dashboard."""

from __future__ import annotations

from collections import Counter
from typing import Any

from services.explore_service import list_universities


def _count_bool(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    yes = no = unknown = 0
    for row in rows:
        val = row.get(key)
        if val is True:
            yes += 1
        elif val is False:
            no += 1
        else:
            unknown += 1
    return {"yes": yes, "no": no, "unknown": unknown}


def _fee_buckets(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Bucket semester-ish fees only; credit-hour figures stay separate."""
    buckets = {
        "Under 50k": 0,
        "50k – 150k": 0,
        "150k – 400k": 0,
        "400k+": 0,
    }
    credit_hour = 0
    unknown = 0
    for r in rows:
        amount = r.get("fee_amount")
        period = (r.get("fee_period") or "").lower()
        if amount in (None, "", 0):
            unknown += 1
            continue
        try:
            n = float(amount)
        except (TypeError, ValueError):
            unknown += 1
            continue
        if "credit" in period:
            credit_hour += 1
            continue
        if n < 50_000:
            buckets["Under 50k"] += 1
        elif n < 150_000:
            buckets["50k – 150k"] += 1
        elif n < 400_000:
            buckets["150k – 400k"] += 1
        else:
            buckets["400k+"] += 1
    return {
        "labels": list(buckets.keys()) + ["Per credit hour", "No fee listed"],
        "values": list(buckets.values()) + [credit_hour, unknown],
    }


def _period_mix(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    for r in rows:
        if r.get("fee_amount") in (None, "", 0):
            counts["No fee listed"] += 1
            continue
        period = (r.get("fee_period") or "unspecified").replace("_", " ").strip().title()
        counts[period or "Unspecified"] += 1
    labels = list(counts.keys())
    return {"labels": labels, "values": [counts[l] for l in labels]}


def _completeness(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fields = [
        ("Fee", "fee_amount"),
        ("Eligibility %", "eligibility"),
        ("Hostel flag", "hostel"),
        ("Sector flag", "is_public"),
        ("Website", "website"),
        ("Programs", "program_count"),
    ]
    labels: list[str] = []
    values: list[float] = []
    for label, key in fields:
        labels.append(label)
        present = 0
        for r in rows:
            val = r.get(key)
            if key == "program_count":
                present += 1 if int(val or 0) > 0 else 0
            elif key in ("hostel", "is_public"):
                present += 1 if val is not None else 0
            elif key == "website":
                present += 1 if val else 0
            else:
                present += 1 if val not in (None, "", 0) else 0
        values.append(round(100 * present / len(rows), 1) if rows else 0)
    return {"labels": labels, "values": values}


def _top_program_keywords(rows: list[dict[str, Any]], limit: int = 8) -> dict[str, Any]:
    keywords = [
        ("Computer Science", ("computer science", "bs cs", "bscs", "software")),
        ("Engineering", ("engineering", "electrical", "mechanical", "civil")),
        ("Business / BBA", ("bba", "business", "management", "commerce")),
        ("Data / AI", ("data science", "artificial intelligence", "ai ", "machine learning")),
        ("Media / Design", ("media", "design", "communication")),
        ("Medicine / Health", ("medical", "health", "pharmacy", "nursing")),
        ("Law", ("law", "llb")),
        ("Social Sciences", ("social", "psychology", "economics", "english")),
    ]
    counts = {name: 0 for name, _ in keywords}
    for r in rows:
        blob = " ".join(r.get("programs") or []).lower()
        for name, needles in keywords:
            if any(n in blob for n in needles):
                counts[name] += 1
    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    return {"labels": [n for n, _ in ranked], "values": [v for _, v in ranked]}


def _scatter_fee_eligibility(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Include every school that has fee + eligibility.
    Credit-hour fees are converted with a 15-credit estimate so all points plot."""
    points = []
    for r in rows:
        amount = r.get("fee_amount")
        elig = r.get("eligibility")
        if amount in (None, "", 0) or elig in (None, ""):
            continue
        try:
            fee = float(amount)
            x = float(elig)
        except (TypeError, ValueError):
            continue
        period = (r.get("fee_period") or "").lower()
        estimated = False
        if "credit" in period:
            fee = fee * 15
            estimated = True
        points.append(
            {
                "x": x,
                "y": fee,
                "label": r["name"],
                "period": (r.get("fee_period") or "unspecified").replace("_", " "),
                "estimated": estimated,
            }
        )
    return {"points": points}


def _all_schools_matrix(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compact per-school metrics table for the analytics UI."""
    matrix = []
    for r in rows:
        amount = r.get("fee_amount")
        period = (r.get("fee_period") or "").lower()
        semester_est = None
        if amount not in (None, "", 0):
            try:
                fee = float(amount)
                semester_est = fee * 15 if "credit" in period else fee
            except (TypeError, ValueError):
                semester_est = None
        matrix.append(
            {
                "id": r["id"],
                "name": r["name"],
                "fee_label": r.get("fee_label") or "—",
                "semester_est": semester_est,
                "eligibility": r.get("eligibility"),
                "hostel": r.get("hostel"),
                "is_public": r.get("is_public"),
                "scholarships": bool(r.get("has_scholarships")),
                "programs": int(r.get("program_count") or 0),
            }
        )
    return {"rows": matrix}


def _insights(rows: list[dict[str, Any]], summary: dict[str, Any]) -> list[str]:
    insights: list[str] = []
    if summary["private"] > summary["public"]:
        insights.append(
            f"Private schools dominate this dataset ({summary['private']} private vs {summary['public']} public)."
        )
    if summary["hostel_yes"] < summary["total"] / 2:
        insights.append(
            f"Only {summary['hostel_yes']} of {summary['total']} schools clearly list on-campus hostel options — "
            "commute or private housing planning matters for many applicants."
        )
    fee_rows = [
        r for r in rows
        if r.get("fee_amount") not in (None, "", 0) and "credit" not in (r.get("fee_period") or "").lower()
    ]
    if fee_rows:
        cheapest = min(fee_rows, key=lambda r: float(r["fee_amount"]))
        priciest = max(fee_rows, key=lambda r: float(r["fee_amount"]))
        insights.append(
            f"Among semester-style fees, {cheapest['name']} looks lowest "
            f"({int(float(cheapest['fee_amount'])):,} PKR) and {priciest['name']} highest "
            f"({int(float(priciest['fee_amount'])):,} PKR)."
        )
    elig_rows = [r for r in rows if r.get("eligibility") not in (None, "")]
    if elig_rows:
        toughest = max(elig_rows, key=lambda r: float(r["eligibility"]))
        insights.append(
            f"Strictest listed eligibility cut-off is {toughest['name']} at {toughest['eligibility']}%."
        )
    incomplete = sum(
        1
        for r in rows
        if r.get("fee_amount") in (None, "", 0) or r.get("eligibility") in (None, "")
    )
    if incomplete:
        insights.append(
            f"{incomplete} school(s) are missing fee or eligibility figures — ask UniMate for those specifics."
        )
    rich_programs = sorted(rows, key=lambda r: int(r.get("program_count") or 0), reverse=True)[:1]
    if rich_programs and int(rich_programs[0].get("program_count") or 0) > 0:
        top = rich_programs[0]
        insights.append(
            f"{top['name']} has the widest indexed program list ({top['program_count']} entries)."
        )
    return insights


def build_analytics() -> dict[str, Any]:
    rows = list_universities()
    sector = _count_bool(rows, "is_public")
    hostel = _count_bool(rows, "hostel")
    with_scholarships = sum(1 for r in rows if r.get("has_scholarships"))
    without_scholarships = len(rows) - with_scholarships

    fee_labels: list[str] = []
    fee_values: list[float] = []
    fee_periods: list[str] = []
    for r in rows:
        amount = r.get("fee_amount")
        if amount in (None, "", 0):
            continue
        try:
            fee_values.append(float(amount))
        except (TypeError, ValueError):
            continue
        fee_labels.append(r["name"])
        fee_periods.append((r.get("fee_period") or "unspecified").replace("_", " "))

    eligibility_labels: list[str] = []
    eligibility_values: list[float] = []
    for r in rows:
        elig = r.get("eligibility")
        if elig in (None, ""):
            continue
        try:
            eligibility_values.append(float(elig))
        except (TypeError, ValueError):
            continue
        eligibility_labels.append(r["name"])

    program_labels = [r["name"] for r in rows]
    program_values = [int(r.get("program_count") or 0) for r in rows]

    known_fees = fee_values
    summary = {
        "total": len(rows),
        "public": sector["yes"],
        "private": sector["no"],
        "hostel_yes": hostel["yes"],
        "scholarships": with_scholarships,
        "avg_fee": round(sum(known_fees) / len(known_fees), 0) if known_fees else None,
        "fee_coverage": len(known_fees),
        "avg_eligibility": (
            round(sum(eligibility_values) / len(eligibility_values), 1)
            if eligibility_values
            else None
        ),
        "median_programs": (
            sorted(program_values)[len(program_values) // 2] if program_values else 0
        ),
    }

    return {
        "summary": summary,
        "insights": _insights(rows, summary),
        "charts": {
            "sector": {
                "labels": ["Public", "Private", "Unknown"],
                "values": [sector["yes"], sector["no"], sector["unknown"]],
            },
            "hostel": {
                "labels": ["Hostel available", "No hostel", "Unknown"],
                "values": [hostel["yes"], hostel["no"], hostel["unknown"]],
            },
            "scholarships": {
                "labels": ["Offers scholarships", "Not listed"],
                "values": [with_scholarships, without_scholarships],
            },
            "fees": {
                "labels": fee_labels,
                "values": fee_values,
                "periods": fee_periods,
            },
            "fee_buckets": _fee_buckets(rows),
            "fee_periods": _period_mix(rows),
            "eligibility": {
                "labels": eligibility_labels,
                "values": eligibility_values,
            },
            "programs": {
                "labels": program_labels,
                "values": program_values,
            },
            "completeness": _completeness(rows),
            "program_themes": _top_program_keywords(rows),
            "fee_vs_eligibility": _scatter_fee_eligibility(rows),
            "schools_matrix": _all_schools_matrix(rows),
        },
    }
