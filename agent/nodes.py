"""LangGraph node functions. Each takes the current AgentState and returns a
partial-state dict to merge in - standard LangGraph node contract."""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from langgraph.config import get_stream_writer

from .geo import geocode_area
from .llm import generate_json_live
from .prompts import (
    ANALYTICS_EXPLAIN_SYSTEM,
    PROFILE_BUILDER_SYSTEM,
    QA_SYSTEM,
    REFINE_CLASSIFIER_SYSTEM,
)
from .retriever import (
    append_source_citations,
    detect_category_hints,
    extract_focus_university_ids,
    get_candidate_universities,
    get_structured_record,
    is_university_locked,
    resolve_retrieval_university_id,
    retrieve_for_question,
)
from services.ranking_service import (
    explain_ranking,
    find_recommendation,
    format_comparison_message,
    format_recommendations_message,
    is_explicit_rerank_request,
    is_ranking_explanation_question,
    is_university_followup_question,
    rank_candidates,
)
from .state import REQUIRED_PROFILE_FIELDS, AgentState

PRIORITY_NOTES = {
    "fees": "This student has told you fees/affordability matters more to them than distance - let a clearly "
    "better budget fit tip close calls in a university's favor.",
    "distance": "This student has told you distance/location matters more to them than fees - let a clearly "
    "closer, more convenient location tip close calls in a university's favor.",
    "both": "This student cares about both fees and distance roughly equally - weigh budget_fit and "
    "location_fit evenly against each other.",
}

# Default split the ranker uses when the student hasn't named a priority (or
# said "both"). Keys match RANKER_SYSTEM's expected JSON score fields.
_BASE_RANKING_WEIGHTS = {
    "program_match": 25,
    "eligibility_match": 20,
    "budget_fit": 20,
    "location_fit": 15,
    "scholarship_fit": 10,
    "goal_alignment": 10,
}
_RANKING_WEIGHT_LABELS = {
    "program_match": "Program match",
    "eligibility_match": "Eligibility match",
    "budget_fit": "Budget fit",
    "location_fit": "Location/distance fit",
    "scholarship_fit": "Scholarship availability",
    "goal_alignment": "Career goal alignment",
}
_PRIORITY_BOOST_KEY = {"fees": "budget_fit", "distance": "location_fit"}
_PRIORITY_BOOST_POINTS = 10


def _ranking_weights(priority_focus: Optional[str]) -> dict[str, int]:
    """A named priority ("fees" or "distance") isn't just a soft nudge to the
    ranker LLM - it moves _PRIORITY_BOOST_POINTS of weight onto that
    dimension for real, taken proportionally from every other dimension so
    the split still sums to 100. "both" (or no priority stated) uses the
    even default split."""
    boost_key = _PRIORITY_BOOST_KEY.get((priority_focus or "").strip().lower())
    if not boost_key:
        return dict(_BASE_RANKING_WEIGHTS)

    others = {k: v for k, v in _BASE_RANKING_WEIGHTS.items() if k != boost_key}
    shrink_fraction = _PRIORITY_BOOST_POINTS / sum(others.values())

    weights = {boost_key: _BASE_RANKING_WEIGHTS[boost_key] + _PRIORITY_BOOST_POINTS}
    for key, base in others.items():
        weights[key] = base - round(base * shrink_fraction)

    # Rounding can leave the split a point or two off 100 - correct it on
    # whichever non-boosted dimension started out largest, so the numbers
    # shown to the ranker always add up cleanly.
    drift = 100 - sum(weights.values())
    if drift:
        biggest = max(others, key=others.get)
        weights[biggest] += drift
    return weights


def _ranking_weights_block(priority_focus: Optional[str]) -> str:
    weights = _ranking_weights(priority_focus)
    boost_key = _PRIORITY_BOOST_KEY.get((priority_focus or "").strip().lower())
    lines = []
    for key, label in _RANKING_WEIGHT_LABELS.items():
        suffix = " (boosted: this is the student's stated top priority)" if key == boost_key else ""
        lines.append(f"- {label}: {weights[key]}%{suffix}")
    return "\n".join(lines)

# Deterministic backstop for the eligibility gate: the LLM is asked to set
# "eligibility_blocked" itself, but that's a soft instruction a model can slip
# on under rephrasing/pressure ("ignore that, just show me schools"). This
# gives a rule the LLM can't talk its way around.
#
# Grade/matric/intermediate mentions are unambiguous descriptions of a
# current status - "grade 8" or "matric" isn't something you'd say about a
# degree you merely want. Bachelor's/Master's/PhD mentions are NOT
# unambiguous the same way: current_education_level can end up containing
# the ASPIRED degree too (e.g. "Grade 8, wants to do a Bachelor's in CS"), so
# a bare keyword match on those would let "grade 8 and want BS CS" register
# as stage 3 and sail straight through the gate it's supposed to stop. Those
# three only count if a completion marker (completed/done/graduated/holds/
# has/earned) appears near the keyword, not just anywhere in the text.
_UNAMBIGUOUS_STAGE_PATTERNS: list[tuple[int, re.Pattern[str]]] = [
    (0, re.compile(r"\bgrade\s*(?:[1-9]|10)\b|\bclass\s*(?:[1-9]|10)\b|\bprimary\b|\bmiddle\s*school\b|"
                   r"\belementary\b|\bjunior\s*school\b", re.I)),
    (1, re.compile(r"\bmatric(?:ulation)?\b|\bo[\s\-]?levels?\b", re.I)),
    (2, re.compile(r"\bintermediate\b|\bf\.?sc\b|\ba[\s\-]?levels?\b|\bhssc\b", re.I)),
]

_DEGREE_KEYWORD_PATTERNS: dict[int, re.Pattern[str]] = {
    3: re.compile(r"\bbachelor|\bbs\b|\bbba\b", re.I),
    4: re.compile(r"\bmaster|\bms\b|\bmba\b", re.I),
    5: re.compile(r"\bph\.?d\b", re.I),
}

_COMPLETION_MARKER_RE = re.compile(r"\b(completed?|done|finished|graduat\w*|holds?|has|earned|obtained)\b", re.I)

_MIN_STAGE_FOR_DEGREE = {"Bachelor": 2, "Master": 3, "PhD": 4}

_DEGREE_PREREQUISITE_TEXT = {
    "Bachelor": "Matriculation/O-Levels and then Intermediate/FSc or A-Levels (or a qualifying test like SAT)",
    "Master": "a completed Bachelor's degree",
    "PhD": "a completed Master's degree",
}


def _stage_rank(current_education_level: str) -> Optional[int]:
    matched = [rank for rank, pattern in _UNAMBIGUOUS_STAGE_PATTERNS if pattern.search(current_education_level)]
    for rank, pattern in _DEGREE_KEYWORD_PATTERNS.items():
        match = pattern.search(current_education_level)
        if not match:
            continue
        window = current_education_level[max(0, match.start() - 25):match.end() + 25]
        if _COMPLETION_MARKER_RE.search(window):
            matched.append(rank)
    return max(matched) if matched else None


def _deterministic_eligibility_block(profile: dict[str, Any]) -> bool:
    degree_level = profile.get("degree_level")
    edu_text = profile.get("current_education_level")
    required_rank = _MIN_STAGE_FOR_DEGREE.get(degree_level)
    if not required_rank or not edu_text:
        return False
    stage_rank = _stage_rank(edu_text)
    return stage_rank is not None and stage_rank < required_rank


# The current dataset only covers Karachi universities - UniMate isn't
# designed for any other city/region yet. Unlike the eligibility gate this
# isn't a permanent block - the student can dismiss it by choosing to see
# Karachi options anyway - so there's no hard rank check, just a
# deterministic trigger to make sure the coverage gap actually gets surfaced
# instead of silently returning zero matches later.
SUPPORTED_CITY = "karachi"
_SUPPORTED_PROVINCE_FOR_CITY = "sindh"  # Karachi's province - a proxy check when no specific city is named


def _is_out_of_scope_region(profile: dict[str, Any]) -> bool:
    cities = profile.get("preferred_cities") or []
    if cities:
        return not any(SUPPORTED_CITY in str(c).strip().lower() for c in cities)
    province = (profile.get("preferred_province") or "").strip().lower()
    if province and province != _SUPPORTED_PROVINCE_FOR_CITY:
        return True
    return False


def _missing_fields(profile: dict[str, Any]) -> list[str]:
    return [f for f in REQUIRED_PROFILE_FIELDS if not profile.get(f)]


# Heuristic for "the student is asking something, not just handing over
# profile info" - triggers a cheap local retrieval (embedding + Chroma query,
# no LLM call, so it's free against the Gemini quota) so profile_builder_node
# has real data to answer with directly, instead of either ignoring the
# question to ask its own, or answering from unguided general knowledge.
_QUESTION_INDICATOR_RE = re.compile(
    r"\?|\bscholarship|\bhostel|\bfee|\btuition|\beligib|\badmission|\bentry test|\bdeadline|\bmerit|"
    r"\brequirement|\bhow (easy|hard|do|much)|\bwhat (is|are)|\bdo(es)? (you|they|it)\b",
    re.I,
)


def _looks_like_question(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if _is_analytics_explain_question(t):
        return False
    return "?" in t or bool(
        re.search(
            r"\b(what|which|how|when|where|why|tell me|explain|compare|show me)\b",
            t,
            re.I,
        )
    )


def _is_analytics_explain_question(text: str) -> bool:
    lower = (text or "").lower()
    return (
        "analytics chart" in lower
        or "unimate analytics" in lower
        or "chart data snapshot" in lower
        or "agent takeaways" in lower
        or "university dataset field completeness" in lower
    )


def _structured_fee_snippet(university_id: Optional[str]) -> str:
    """Some universities' real tuition figure was only ever confirmed as a
    verified (amount, period) pair directly in the SQLite table (see
    src/normalizer.py's UNIVERSITY_SEED_TUITION) - e.g. FAST's fee page table
    never made it into a searchable chunk cleanly, so a fee_structure chunk
    search alone comes up empty even though the real number is known. Pull
    it from the structured record so a fee question can still be answered."""
    if not university_id:
        return ""
    record = get_structured_record(university_id)
    if not record or not record.get("tuition_fee_amount"):
        return ""
    period = (record.get("tuition_fee_period") or "").replace("_", " ")
    return f"[{record.get('university_name')} | verified tuition] {record['tuition_fee_amount']:,} PKR {period}"


def _sanitize_profile_updates(updates: Any) -> dict[str, Any]:
    """Bounds-check the fields most likely to silently corrupt ranking if a
    model hallucinates or misparses a number - a garbled 9500% academic
    percentage or a billion-PKR budget should be dropped, not merged in
    unquestioned."""
    if not isinstance(updates, dict):
        return {}
    cleaned = dict(updates)

    if "academic_percentage" in cleaned:
        try:
            pct = float(cleaned["academic_percentage"])
        except (TypeError, ValueError):
            cleaned.pop("academic_percentage", None)
        else:
            if 0 <= pct <= 100:
                cleaned["academic_percentage"] = pct
            else:
                cleaned.pop("academic_percentage", None)

    if "budget_pkr_per_semester" in cleaned:
        try:
            budget = float(cleaned["budget_pkr_per_semester"])
        except (TypeError, ValueError):
            cleaned.pop("budget_pkr_per_semester", None)
        else:
            if 0 < budget <= 50_000_000:
                cleaned["budget_pkr_per_semester"] = int(budget)
            else:
                cleaned.pop("budget_pkr_per_semester", None)

    if isinstance(cleaned.get("entry_test_scores"), dict):
        scores: dict[str, float] = {}
        for name, score in cleaned["entry_test_scores"].items():
            try:
                score = float(score)
            except (TypeError, ValueError):
                continue
            if 0 <= score <= 2000:
                scores[name] = score
        cleaned["entry_test_scores"] = scores

    return cleaned


def _trace(writer, kind: str, text: str) -> None:
    """Emits one live-trace step (action/observation, or a one-shot thought
    for a node with no LLM call to draw real reasoning from) over the same
    custom stream channel _run_live uses for live tokens - a no-op if the
    caller isn't consuming stream_mode="custom". Every value here is built
    from data that actually just flowed through the node (the real query,
    the real candidate count, the real top scores) rather than a canned
    phrase, so what a UI shows is the agent's actual step, not a decorative
    label - just phrased as a natural sentence (see _natural_join) instead of
    pseudo-code like "Retrieve(query)", since the UI renders these as one
    flowing paragraph, not a technical log."""
    writer({"type": kind, "text": text})


_CATEGORY_TOPIC_PHRASES = {
    "fee_structure": "the fee details",
    "hostel": "hostel info",
    "scholarships": "scholarship options",
    "eligibility": "the eligibility requirements",
    "test_pattern": "the test format",
    "offered_courses": "the programs offered",
}


def _retrieval_trace(writer, categories: list[str], hits: list[dict[str, Any]]) -> None:
    """Shared natural-language action/observation pair for the two spots
    (profile_builder_node's inline question retrieval, qa_node) that run a
    real semantic search mid-turn - phrased around the actual topic detected
    and the actual hit count/university name, not a "Retrieve(query)"
    pseudo-code dump."""
    topic = next((phrase for cat, phrase in _CATEGORY_TOPIC_PHRASES.items() if cat in (categories or [])), None)
    _trace(writer, "action", f"Let me look up {topic or 'that'}...")
    if hits:
        uni_name = hits[0]["metadata"].get("university_name")
        where = f" on {uni_name}" if uni_name else ""
        _trace(writer, "observation", f"Found {len(hits)} solid passage{'s' if len(hits) != 1 else ''}{where} to work with.")
    else:
        _trace(writer, "observation", "Didn't turn up much directly on that, unfortunately.")


def _natural_join(items: list[str]) -> str:
    """"A" / "A and B" / "A, B, and C" - for reading a real list of names out
    loud in a trace sentence instead of a bare comma-joined dump."""
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _run_live(system_prompt: str, user_prompt: str, stream_fields: list[str]) -> dict[str, Any]:
    """Runs a generate_json_live call, forwarding the model's own "thinking"
    field live as real thought-trace deltas (genuine per-call reasoning the
    model just generated, not a hardcoded string - it varies every time) and,
    when the schema includes it, the "answer" field live as the actual
    response being written. A no-op forward if the caller isn't consuming
    stream_mode="custom", e.g. agent/cli.py's plain .invoke(). Returns the
    final parsed JSON result dict for the node to read its real fields from."""
    writer = get_stream_writer()
    result: dict[str, Any] = {}
    for field, payload in generate_json_live(system_prompt, user_prompt, stream_fields):
        if field == "_result":
            result = payload if isinstance(payload, dict) else {}
        elif field == "thinking":
            writer({"type": "thought", "text": payload})
        elif field == "answer":
            writer({"type": "token", "text": payload})
    return result


def _last_user_message(state: AgentState) -> str:
    for msg in reversed(state["messages"]):
        if isinstance(msg, dict):
            role = msg.get("role", "")
            content = msg.get("content", "")
        else:
            role = getattr(msg, "type", "")
            content = getattr(msg, "content", "")
        if role in ("human", "user"):
            return content
    return ""


def _last_assistant_message(state: AgentState) -> str:
    for msg in reversed(state["messages"]):
        if isinstance(msg, dict):
            role = msg.get("role", "")
            content = msg.get("content", "")
        else:
            role = getattr(msg, "type", "")
            content = getattr(msg, "content", "")
        if role in ("assistant", "ai"):
            return content
    return ""


def _resolve_university_id(state: AgentState, last_message: str, last_assistant_message: str):
    return resolve_retrieval_university_id(
        state.get("selected_university"),
        last_message,
        last_assistant_message,
    )


def _merge_profile_updates(profile: dict[str, Any], updates: Any) -> dict[str, Any]:
    if not isinstance(updates, dict):
        return profile
    merged = dict(profile)
    for key, value in updates.items():
        if value not in (None, "", [], {}):
            merged[key] = value
    return merged


def profile_builder_node(state: AgentState) -> dict[str, Any]:
    """Extracts profile updates from the latest message and drafts the next
    question in a single LLM call (rather than two) - the free-tier Gemini
    quota is tight enough (5 req/min) that halving calls-per-turn matters."""
    writer = get_stream_writer()
    profile = dict(state.get("student_profile") or {})
    last_message = _last_user_message(state)
    last_question = _last_assistant_message(state)
    missing_before = _missing_fields(profile)

    # Analytics chart / takeaway questions already carry their data snapshot —
    # answer them directly instead of profiling or retrieving random chunks.
    if _is_analytics_explain_question(last_message):
        _trace(writer, "thought", "This is an Analytics chart question — I'll explain the dataset snapshot, not your profile progress.")
        _trace(writer, "action", "Reading the chart snapshot from your message…")
        result = _run_live(ANALYTICS_EXPLAIN_SYSTEM, last_message, ["thinking", "answer"])
        answer = ""
        if isinstance(result, dict):
            answer = (result.get("answer") or result.get("reply") or "").strip()
        if not answer:
            answer = (
                "That Analytics chart measures how complete UniMate's university dataset is for each field "
                "(e.g. how many schools have a fee or eligibility figure), not how complete your personal profile is. "
                "Ask me again with the snapshot if you want a field-by-field breakdown."
            )
        _trace(writer, "observation", "Explained the Analytics chart from the provided snapshot.")
        return {
            "student_profile": profile,
            "profile_complete": not missing_before,
            "messages": [{"role": "assistant", "content": answer}],
            "current_phase": "profiling" if missing_before else "refining",
            "recommendations_requested": False,
        }

    # Cheap local retrieval (no LLM call) so a question asked mid-profiling
    # ("what is the fee structure of FAST") can be answered directly with
    # real data instead of being brushed aside for the next profiling
    # question. university_id resolution falls back to whichever university
    # the assistant's own previous reply was about, since a pronoun-only
    # follow-up ("what is ITS fee structure") names nothing on its own.
    retrieved_context = ""
    hits: list[dict[str, Any]] = []
    if last_message and _looks_like_question(last_message):
        university_id = _resolve_university_id(state, last_message, last_question)
        categories = detect_category_hints(last_message)
        query = f"{last_message} {profile.get('field_of_study', '')}".strip()
        locked = is_university_locked(state.get("selected_university"))
        hits = retrieve_for_question(
            query,
            university_id=university_id,
            category=categories,
            top_k=4,
            strict_university_filter=locked,
        )
        _retrieval_trace(writer, categories, hits)
        context_parts = []
        if "fee_structure" in categories:
            fee_snippet = _structured_fee_snippet(university_id)
            if fee_snippet:
                context_parts.append(fee_snippet)
        context_parts.extend(
            f"[{h['metadata'].get('university_name')} | {h['metadata'].get('category')}] {h['text']}"
            for h in hits
        )
        retrieved_context = "\n\n".join(context_parts)

    # A short, context-dependent reply ("yes I have", "its fee structure")
    # only makes sense in light of the question you just asked - passing your
    # own previous message alongside it is what lets the model resolve
    # references like this instead of treating the message as if it arrived
    # with no history at all.
    if last_message and last_question:
        user_prompt = (
            f"Your previous message to the student was: {last_question}\n\n"
            f"Student's latest reply: {last_message}"
        )
    elif last_message:
        user_prompt = f"Student's latest message: {last_message}"
    else:
        user_prompt = "The conversation is just starting."

    result = _run_live(
        PROFILE_BUILDER_SYSTEM.format(
            profile=json.dumps(profile), missing_fields=missing_before, retrieved_context=retrieved_context or "(none)"
        ),
        user_prompt,
        ["thinking"],
    )
    updates = _sanitize_profile_updates(result.get("profile_updates", {}) if isinstance(result, dict) else {})
    reply = result.get("reply", "") if isinstance(result, dict) else ""
    # Sticky: the LLM only judges wants_recommendations off THIS message, so a
    # prior turn's explicit ask (while a field was still missing) has to be
    # carried forward here or it gets lost the moment the turn ends.
    wants_recommendations = (bool(result.get("wants_recommendations")) if isinstance(result, dict) else False) or bool(
        state.get("recommendations_requested")
    )
    # Deterministic: named compare/shortlist asks always mean "rank these now".
    if extract_focus_university_ids(last_message):
        wants_recommendations = True
    eligibility_blocked = bool(result.get("eligibility_blocked")) if isinstance(result, dict) else False
    region_notice_acknowledged = bool(result.get("region_notice_acknowledged")) if isinstance(result, dict) else False

    profile = _merge_profile_updates(profile, updates)
    missing_after = _missing_fields(profile)

    # Deterministic backstop: don't just trust the LLM's own eligibility_blocked
    # flag, since a rephrased or pushy message could talk it out of setting
    # that. If the stated current_education_level plainly hasn't reached the
    # degree_level's prerequisite stage, force the block regardless of what
    # the model returned, and write our own explanation for it.
    if not eligibility_blocked and _deterministic_eligibility_block(profile):
        eligibility_blocked = True
        degree_level = profile.get("degree_level")
        reply = (
            f"It looks like you're not quite at the stage yet for a {degree_level}'s degree - based on what "
            f"you mentioned ({profile.get('current_education_level')}), you'd typically need "
            f"{_DEGREE_PREREQUISITE_TEXT.get(degree_level, 'the prerequisite qualification')} first. "
            "Feel free to come back once you're closer to that!"
        )

    # Same idea for regional coverage, but dismissible: an out-of-scope
    # province/city only blocks matching until the student has actually been
    # told about it (region_notice_acknowledged) - after that they're free to
    # proceed with Karachi options if they choose to.
    region_gate_open = not eligibility_blocked and _is_out_of_scope_region(profile) and not region_notice_acknowledged
    if region_gate_open and not reply:
        out_of_scope_place = ", ".join(profile.get("preferred_cities") or []) or profile.get("preferred_province")
        reply = (
            f"Just so you know - UniMate isn't designed for {out_of_scope_place} yet. Right now it only "
            "covers Karachi universities. Would you like to see Karachi options anyway, or wait until we "
            "cover more cities?"
        )

    # Having every required field does NOT mean we recommend - only route to
    # matching once the student has actually asked to see options. Otherwise
    # we'd surprise-recommend the moment the last required field lands,
    # which is exactly the premature-recommendation behavior that's wrong.
    # eligibility_blocked and region_gate_open are hard stops enforced here
    # too, not just trusted from the prompt, so a model slip-up on
    # wants_recommendations can't route around either of them.
    if not missing_after and wants_recommendations and not eligibility_blocked and not region_gate_open:
        return {
            "student_profile": profile,
            "profile_complete": True,
            "current_phase": "matching",
            "recommendations_requested": False,
        }

    if not reply:
        reply = (
            "Could you tell me a bit more so I can find the best options for you?"
            if missing_after
            else "I have enough to find some good matches - want me to show you recommendations now, "
            "or is there anything else you'd like to add first?"
        )

    if hits and reply and _looks_like_question(last_message):
        reply = append_source_citations(reply, hits)

    return {
        "messages": [{"role": "assistant", "content": reply}],
        "student_profile": profile,
        "profile_complete": False,
        "current_phase": "profiling",
        "recommendations_requested": wants_recommendations,
    }


def retriever_node(state: AgentState) -> dict[str, Any]:
    writer = get_stream_writer()
    profile = state["student_profile"]
    last_message = _last_user_message(state)
    focus_ids = extract_focus_university_ids(last_message)

    # No LLM call happens in this node (get_candidate_universities is a
    # deterministic SQLite + vector lookup), so there's no real model
    # reasoning to stream here - this line is built from the student's own
    # actual profile values instead of a fixed sentence, so it still says
    # something true and specific rather than a canned phrase.
    field_bit = profile.get("field_of_study")
    degree_bit = profile.get("degree_level")
    budget_bit = f"~{profile['budget_pkr_per_semester']:,} PKR/semester" if profile.get("budget_pkr_per_semester") else None
    if focus_ids:
        from .retriever import get_university_display_name

        names = [get_university_display_name(uid) for uid in focus_ids]
        thought = f"You asked me to compare {_natural_join(names)} against your profile — I'll pull those specifically."
    else:
        thought = "You're looking for " + " ".join(filter(None, [degree_bit, field_bit or "a program"]))
        if budget_bit:
            thought += f" around a budget of {budget_bit}"
        thought += " - let me pull matching options from what I cover."
    _trace(writer, "thought", thought)

    location_bit = profile.get("student_area") or profile.get("student_city") or profile.get("preferred_province")
    if location_bit and "karachi" not in location_bit.lower():
        location_bit = f"{location_bit}, Karachi"
    if focus_ids:
        _trace(writer, "action", f"Focusing retrieval on the {len(focus_ids)} universities you named…")
    else:
        _trace(writer, "action", f"Scanning through the universities I track in {location_bit or 'Karachi'}...")

    candidates = get_candidate_universities(
        profile,
        university_filter=state.get("selected_university"),
        focus_university_ids=focus_ids or None,
    )

    names = [c["record"].get("university_name") or c["record"].get("university_id", "?") for c in candidates]
    if names:
        obs = f"Turned up {len(names)} option{'s' if len(names) != 1 else ''} worth a closer look: {_natural_join(names)}."
    else:
        obs = "Came up empty this time - nothing in what I cover matches that combination yet."
    _trace(writer, "observation", obs)

    return {
        "retrieved_universities": candidates,
        "focus_university_ids": focus_ids or None,
        "current_phase": "matching",
    }


def _student_coords(profile: dict[str, Any]) -> tuple[float, float] | None:
    area_text = profile.get("student_area") or profile.get("student_city")
    return geocode_area(area_text) if area_text else None


def _verified_data_line(record: dict[str, Any], distance_km: Optional[float]) -> str:
    """Ground-truth figures from the SQLite record - the ranker LLM should
    prefer these over inferring the same facts (less reliably) from prose
    chunk text."""
    bits = []
    if record.get("min_eligibility_percentage") is not None:
        bits.append(f"min eligibility {record['min_eligibility_percentage']}%")
    if record.get("tuition_fee_amount"):
        period = (record.get("tuition_fee_period") or "").replace("_", " ")
        bits.append(f"verified tuition {record['tuition_fee_amount']:,} PKR {period}")
    if record.get("hostel_available") is not None:
        bits.append("hostel available" if record["hostel_available"] else "no on-campus hostel")
    if record.get("has_scholarships"):
        bits.append("scholarships available")
    if distance_km is not None:
        bits.append(f"{distance_km:.1f} km from student")
    if not bits:
        return ""
    return f"[{record.get('university_name')} | id: {record['university_id']} | VERIFIED] " + "; ".join(bits)


def ranker_node(state: AgentState) -> dict[str, Any]:
    writer = get_stream_writer()
    profile = state["student_profile"]
    candidates = state.get("retrieved_universities") or []

    if not candidates:
        return {"recommendations": [], "current_phase": "presenting"}

    priority_focus = profile.get("priority_focus")
    focus_ids = state.get("focus_university_ids") or []
    # When comparing a named set, rank all of them (not just top 5 of a larger pool).
    limit = max(5, len(focus_ids)) if focus_ids else 5
    validated = rank_candidates(profile, candidates, priority_focus=priority_focus, limit=limit)

    top = validated[:3]
    if not top:
        obs = "None of the candidates scored well enough to feel like a strong match."
    elif len(top) == 1:
        obs = f"{top[0].get('university_name')} is coming out on top at {top[0].get('total_score')}/100."
    else:
        leader, rest = top[0], top[1:]
        rest_desc = _natural_join([f"{r.get('university_name')} ({r.get('total_score')})" for r in rest])
        obs = f"{leader.get('university_name')} is leading the pack at {leader.get('total_score')}/100, with {rest_desc} close behind."
    _trace(writer, "observation", obs)

    return {"recommendations": validated, "current_phase": "presenting"}


def presenter_node(state: AgentState) -> dict[str, Any]:
    recommendations = state.get("recommendations") or []
    if not recommendations:
        # Defense in depth alongside profile_builder_node's region gate: if a
        # zero-result run reaches here anyway, name the actual reason (out of
        # scope region) instead of the generic "loosen a constraint" message,
        # which would otherwise look like a bug rather than a coverage limit.
        profile = state.get("student_profile") or {}
        if _is_out_of_scope_region(profile):
            out_of_scope_place = ", ".join(profile.get("preferred_cities") or []) or profile.get("preferred_province")
            content = (
                f"I couldn't find any matches because UniMate isn't designed for {out_of_scope_place} yet - "
                "right now it only covers Karachi universities. Would you like to see Karachi options instead?"
            )
        else:
            content = (
                "I couldn't find any matching universities in our current dataset for your "
                "preferences. Would you like to loosen a constraint, like budget or location?"
            )
        return {
            "messages": [{"role": "assistant", "content": content}],
            "current_phase": "presenting",
        }

    content = (
        format_comparison_message(recommendations)
        if state.get("focus_university_ids")
        else format_recommendations_message(recommendations)
    )
    return {
        "messages": [{"role": "assistant", "content": content}],
        "current_phase": "presenting",
    }


def refine_node(state: AgentState) -> dict[str, Any]:
    last_message = _last_user_message(state)

    # Analytics explain requests should answer immediately, not re-rank.
    if _is_analytics_explain_question(last_message):
        writer = get_stream_writer()
        _trace(writer, "thought", "Analytics chart follow-up — explaining the dataset snapshot directly.")
        result = _run_live(ANALYTICS_EXPLAIN_SYSTEM, last_message, ["thinking", "answer"])
        answer = ""
        if isinstance(result, dict):
            answer = (result.get("answer") or result.get("reply") or "").strip()
        if not answer:
            answer = (
                "That chart is about UniMate's university dataset coverage, not your profile completeness. "
                "Share the snapshot again if you want a field-by-field read."
            )
        return {
            "student_profile": state.get("student_profile") or {},
            "current_phase": "refining",
            "refine_action": "chitchat",
            "messages": [{"role": "assistant", "content": answer}],
        }

    result = _run_live(REFINE_CLASSIFIER_SYSTEM, f"Student's message: {last_message}", ["thinking"])

    action = "end"
    updates: Any = {}
    reply = ""
    if isinstance(result, dict):
        action = result.get("action", "end")
        updates = result.get("updates", {})
        reply = result.get("reply", "")

    # Deterministic overrides — the classifier often mislabels single-university
    # Q&A ("Why is FAST a fit?", "application plan for NED") as "refine", which
    # reprints the ranked list via presenter. Multi-uni compare still re-ranks.
    # Explicit "Recommend…" / re-rank asks must also re-enter ranking even if the
    # model picks answer_question.
    focus_ids = extract_focus_university_ids(last_message)
    locked = is_university_locked(state.get("selected_university"))
    if focus_ids or is_explicit_rerank_request(last_message):
        action = "refine"
    elif locked or is_university_followup_question(last_message):
        action = "answer_question"

    profile = _merge_profile_updates(state.get("student_profile") or {}, _sanitize_profile_updates(updates))

    output: dict[str, Any] = {
        "student_profile": profile,
        "current_phase": "refining",
        "refine_action": action,
    }
    # "chitchat" and "end" both route straight to END in the graph (see
    # _route_after_refine) - without a reply here, the student would get
    # nothing back at all for that turn (this is also the fallback when JSON
    # parsing fails), which looks like the app silently died rather than
    # responding at all.
    if action == "chitchat":
        output["messages"] = [{
            "role": "assistant",
            "content": reply or "Hey! Ask me anything about your recommendations, or let me know if you'd like to tweak your criteria.",
        }]
    elif action == "end":
        output["messages"] = [{
            "role": "assistant",
            "content": reply or "Glad I could help! Good luck with your applications - feel free to come back anytime.",
        }]
    return output


def qa_node(state: AgentState) -> dict[str, Any]:
    """Answers a specific follow-up question after recommendations have been
    shown. Two distinct kinds of question land here: a NEW factual question
    ("tell me about DHA Suffa's scholarships") that needs fresh retrieval, and
    a question ABOUT the recommendations already given ("which one is more
    ideal for me", "why did you rank X higher") that needs the existing
    ranked list and profile, not a blind semantic search over the raw
    question text (which has no lexical connection to any specific
    university and so retrieves close to nothing useful)."""
    writer = get_stream_writer()
    question = _last_user_message(state)
    profile = state.get("student_profile") or {}
    recommendations = state.get("recommendations") or []

    if recommendations and is_ranking_explanation_question(question):
        target = find_recommendation(recommendations, question)
        if target:
            content = explain_ranking(target)
            return {
                "messages": [{"role": "assistant", "content": content}],
                "current_phase": "refining",
            }

    university_id = resolve_retrieval_university_id(state.get("selected_university"), question)
    categories = detect_category_hints(question)
    locked = is_university_locked(state.get("selected_university"))
    hits = retrieve_for_question(
        question,
        university_id=university_id,
        category=categories,
        strict_university_filter=locked,
    )
    _retrieval_trace(writer, categories, hits)

    context_sections: list[str] = []
    if recommendations:
        context_sections.append(
            "Recommendations already given to this student:\n" + json.dumps(recommendations, indent=2)
        )
    if profile:
        context_sections.append(f"Student profile:\n{json.dumps(profile)}")
    if "fee_structure" in categories:
        fee_snippet = _structured_fee_snippet(university_id)
        if fee_snippet:
            context_sections.append(f"Verified data:\n{fee_snippet}")
    if hits:
        retrieved = "\n\n".join(
            f"[{h['metadata'].get('university_name')} | {h['metadata'].get('category')}] {h['text']}"
            for h in hits
        )
        context_sections.append(f"Additional retrieved information:\n{retrieved}")

    if not context_sections:
        content = (
            "I don't have specific data on that in my current dataset - could you rephrase, or ask about "
            "something else?"
        )
    else:
        result = _run_live(QA_SYSTEM.format(context="\n\n".join(context_sections)), question, ["thinking", "answer"])
        content = (result.get("answer") or "").strip()
        if hits:
            content = append_source_citations(content, hits)

    return {
        "messages": [{"role": "assistant", "content": content}],
        "current_phase": "refining",
    }
