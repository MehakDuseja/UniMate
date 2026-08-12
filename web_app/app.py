from __future__ import annotations

import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, Response, jsonify, redirect, render_template, request, session, send_file
import json
from io import BytesIO

from agent.graph import build_graph
from agent.state import initial_state
from services import (
    analytics_service,
    bootstrap_service,
    conversation_service,
    explore_service,
    export_service,
    profile_service,
    recommendations_store,
)

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-unimate-please-change")

_graph = None
_bootstrapped = False


def ensure_data_ready() -> None:
    global _bootstrapped
    if _bootstrapped:
        return
    try:
        status = bootstrap_service.ensure_retrieval_stores()
        app.logger.info("Retrieval stores ready: %s", status)
    except Exception as exc:
        app.logger.exception("Bootstrap failed (chat will use structured fallbacks): %s", exc)
    _bootstrapped = True


@app.before_request
def _before_request_bootstrap():
    # Avoid blocking static assets on first hit.
    if request.path.startswith("/static"):
        return
    ensure_data_ready()


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def get_or_create_student() -> str:
    sid = session.get("student_session_id")
    if not sid:
        sid = str(uuid.uuid4())
        session["student_session_id"] = sid
    return profile_service.ensure_student(sid)


def _saved_profile_bundle() -> dict:
    student_id = get_or_create_student()
    saved = profile_service.get_saved_profile(student_id) or {}
    profile = saved.get("profile") or {}
    missing = profile_service.missing_required_fields(profile)
    return {
        "student_id": student_id,
        "saved": saved,
        "profile": profile,
        "profile_ready": not missing,
        "profile_missing": missing,
        "profile_missing_labels": [
            profile_service.REQUIRED_FIELD_LABELS.get(f, f.replace("_", " ")) for f in missing
        ],
        "completeness_pct": int(saved.get("completeness_pct") or 0),
    }


@app.context_processor
def inject_flow_context():
    try:
        bundle = _saved_profile_bundle()
        return {
            "profile_ready": bundle["profile_ready"],
            "profile_missing": bundle["profile_missing"],
            "profile_missing_labels": bundle["profile_missing_labels"],
            "profile_completeness": bundle["completeness_pct"],
        }
    except Exception:
        return {
            "profile_ready": False,
            "profile_missing": list(profile_service.REQUIRED_FOR_CHAT),
            "profile_missing_labels": [
                profile_service.REQUIRED_FIELD_LABELS.get(f, f) for f in profile_service.REQUIRED_FOR_CHAT
            ],
            "profile_completeness": 0,
        }


def _require_profile_ready_api():
    bundle = _saved_profile_bundle()
    if bundle["profile_ready"]:
        return None, bundle
    return (
        jsonify(
            {
                "error": "Complete your profile before chatting with the agent.",
                "missing": bundle["profile_missing"],
                "missing_labels": bundle["profile_missing_labels"],
                "redirect": "/profile?next=chat",
            }
        ),
        403,
    ), bundle


def _role_and_content(msg) -> tuple[str, str]:
    if isinstance(msg, dict):
        role = msg.get("role", "")
        if role in ("human", "user"):
            return "user", msg.get("content", "") or ""
        if role in ("assistant", "ai"):
            return "assistant", msg.get("content", "") or ""
        return role, msg.get("content", "") or ""
    msg_type = getattr(msg, "type", "")
    content = getattr(msg, "content", "") or ""
    if msg_type in ("human", "user"):
        return "user", content
    if msg_type in ("ai", "assistant"):
        return "assistant", content
    return msg_type, content


def _new_assistant_replies(before_count: int, state) -> list[str]:
    replies: list[str] = []
    for msg in (state.get("messages") or [])[before_count:]:
        role, content = _role_and_content(msg)
        if role == "assistant" and content.strip():
            replies.append(content.strip())
    return replies


@app.route("/")
def index():
    bundle = _saved_profile_bundle()
    if not bundle["profile_ready"]:
        return redirect("/profile?next=chat")
    prefill = (request.args.get("q") or "").strip()
    return render_template(
        "index.html",
        completeness_pct=bundle["completeness_pct"],
        prefill_q=prefill,
        profile_ready=True,
    )


@app.route("/profile")
def profile():
    bundle = _saved_profile_bundle()
    next_step = (request.args.get("next") or "").strip()
    return render_template(
        "profile.html",
        profile=bundle["profile"],
        saved_meta=bundle["saved"],
        profile_ready=bundle["profile_ready"],
        profile_missing_labels=bundle["profile_missing_labels"],
        next_step=next_step,
    )


@app.route("/api/profile", methods=["POST"])
def api_save_profile():
    student_id = get_or_create_student()
    data = request.json or {}
    profile = data.get("profile") or {}
    meta = profile_service.save_profile(student_id, profile, mark_saved=True)
    meta["profile_ready"] = profile_service.required_fields_complete(profile)
    meta["missing"] = profile_service.missing_required_fields(profile)
    meta["missing_labels"] = [
        profile_service.REQUIRED_FIELD_LABELS.get(f, f.replace("_", " ")) for f in meta["missing"]
    ]
    return jsonify(meta)


@app.route("/explore")
def explore_page():
    student_id = get_or_create_student()
    payload = explore_service.explore_payload(student_id)
    return render_template(
        "explore.html",
        universities=payload["universities"],
        shortlist_count=payload["shortlist_count"],
    )


@app.route("/analytics")
def analytics_page():
    get_or_create_student()
    payload = analytics_service.build_analytics()
    return render_template(
        "analytics.html",
        summary=payload["summary"],
        charts=payload["charts"],
        insights=payload.get("insights") or [],
    )


@app.route("/api/shortlist", methods=["POST"])
def api_shortlist():
    student_id = get_or_create_student()
    data = request.json or {}
    university_id = (data.get("university_id") or "").strip()
    saved = bool(data.get("saved"))
    if not university_id:
        return jsonify({"error": "university_id required"}), 400
    try:
        result = explore_service.set_shortlisted(student_id, university_id, saved)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    result["shortlist_ids"] = explore_service.get_shortlist_ids(student_id)
    result["shortlist_count"] = len(result["shortlist_ids"])
    return jsonify(result)


@app.route("/api/shortlist", methods=["GET"])
def api_get_shortlist():
    student_id = get_or_create_student()
    items = explore_service.get_shortlist_details(student_id)
    return jsonify({"items": items, "count": len(items)})


@app.route("/api/shortlist/bulk", methods=["POST"])
def api_shortlist_bulk():
    student_id = get_or_create_student()
    data = request.json or {}
    ids = data.get("university_ids") or []
    if not isinstance(ids, list) or not ids:
        ids = [
            r.get("university_id")
            for r in recommendations_store.load_recommendations(student_id)
            if r.get("university_id")
        ]
    if not ids:
        return jsonify({"error": "No universities to shortlist. Run recommendations first."}), 400
    result = explore_service.shortlist_bulk(student_id, [str(x) for x in ids])
    return jsonify(result)


@app.route("/api/recommendations/latest", methods=["GET"])
def api_latest_recommendations():
    student_id = get_or_create_student()
    recs = recommendations_store.load_recommendations(student_id)
    return jsonify({"recommendations": recs, "count": len(recs)})


@app.route("/api/export/recommendations.pdf", methods=["GET", "POST"])
def api_export_recommendations_pdf():
    student_id = get_or_create_student()
    saved = profile_service.get_saved_profile(student_id) or {}
    profile = saved.get("profile") or {}

    recs: list = []
    if request.method == "POST":
        body = request.json or {}
        recs = body.get("recommendations") or []
    if not recs:
        recs = recommendations_store.load_recommendations(student_id)
    if not recs:
        return jsonify({"error": "No recommendations to export. Ask the agent to recommend fits first."}), 400

    pdf_bytes = export_service.build_recommendations_pdf(recs, profile=profile)
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="unimate-recommendations.pdf",
    )


@app.route("/api/export/recommendations.md", methods=["GET", "POST"])
def api_export_recommendations_md():
    student_id = get_or_create_student()
    saved = profile_service.get_saved_profile(student_id) or {}
    profile = saved.get("profile") or {}
    recs: list = []
    if request.method == "POST":
        body = request.json or {}
        recs = body.get("recommendations") or []
    if not recs:
        recs = recommendations_store.load_recommendations(student_id)
    if not recs:
        return jsonify({"error": "No recommendations to export yet."}), 400
    md = export_service.recommendations_markdown(recs, profile=profile)
    return Response(
        md,
        mimetype="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="unimate-recommendations.md"'},
    )


@app.route("/api/export/profile.pdf", methods=["GET"])
def api_export_profile_pdf():
    student_id = get_or_create_student()
    saved = profile_service.get_saved_profile(student_id) or {}
    profile = saved.get("profile") or {}
    if not profile:
        return jsonify({"error": "Save a profile first."}), 400
    pdf_bytes = export_service.build_profile_pdf(
        profile, completeness_pct=int(saved.get("completeness_pct") or 0)
    )
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="unimate-profile.pdf",
    )


@app.route("/api/agent/context", methods=["GET"])
def api_agent_context():
    """Lightweight context so chat tools can personalize prompts."""
    bundle = _saved_profile_bundle()
    shortlist = explore_service.get_shortlist_details(bundle["student_id"])
    recs = recommendations_store.load_recommendations(bundle["student_id"])
    return jsonify(
        {
            "profile": bundle["profile"],
            "completeness_pct": bundle["completeness_pct"],
            "profile_ready": bundle["profile_ready"],
            "missing": bundle["profile_missing"],
            "missing_labels": bundle["profile_missing_labels"],
            "shortlist": shortlist,
            "shortlist_count": len(shortlist),
            "recommendations": recs,
            "recommendations_count": len(recs),
        }
    )


@app.route("/api/conversations", methods=["GET"])
def api_conversations():
    student_id = get_or_create_student()
    return jsonify(conversation_service.list_conversations(student_id))


@app.route("/api/conversations", methods=["POST"])
def api_create_conversation():
    blocked, _bundle = _require_profile_ready_api()
    if blocked:
        return blocked
    student_id = get_or_create_student()
    data = request.json or {}
    title = (data.get("title") or "New Chat").strip() or "New Chat"
    chat_id = conversation_service.create_chat(student_id, title=title)
    return jsonify({"id": chat_id, "title": title})


@app.route("/api/conversations/<thread_id>", methods=["PATCH"])
def api_rename_conversation(thread_id):
    student_id = get_or_create_student()
    conv = conversation_service.get_conversation(thread_id)
    if not conv or conv.get("student_id") != student_id:
        return jsonify({"error": "Conversation not found"}), 404
    data = request.json or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title required"}), 400
    if len(title) > 120:
        title = title[:120].rstrip()
    conversation_service.rename_conversation(thread_id, title)
    return jsonify({"id": thread_id, "title": title})


@app.route("/api/conversations/<thread_id>", methods=["DELETE"])
def api_delete_conversation(thread_id):
    student_id = get_or_create_student()
    conv = conversation_service.get_conversation(thread_id)
    if not conv or conv.get("student_id") != student_id:
        return jsonify({"error": "Conversation not found"}), 404
    conversation_service.delete_conversation(thread_id)
    return jsonify({"ok": True, "id": thread_id})


@app.route("/api/chat/<thread_id>/messages")
def api_get_messages(thread_id):
    student_id = get_or_create_student()
    conv = conversation_service.get_conversation(thread_id)
    if not conv or conv.get("student_id") != student_id:
        return jsonify([])
    return jsonify(conversation_service.get_chat_messages(thread_id))


@app.route("/api/chat/<thread_id>/message", methods=["POST"])
def api_post_message(thread_id):
    blocked, _bundle = _require_profile_ready_api()
    if blocked:
        return blocked

    data = request.json or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "empty"}), 400

    student_id = get_or_create_student()
    conversation_service.upsert_conversation(thread_id=thread_id, student_id=student_id)
    conversation_service.append_message(thread_id, "user", text)

    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    state = _prepare_agent_state(graph, config, student_id, text)
    before_count = len(state.get("messages") or [])

    try:
        state = graph.invoke(state, config=config)
    except Exception as exc:
        fallback = (
            "Sorry — I hit an error talking to the model. "
            "Please try again in a moment."
        )
        conversation_service.append_message(thread_id, "assistant", fallback)
        return jsonify(
            {
                "reply": fallback,
                "replies": [fallback],
                "recommendations": [],
                "error_detail": str(exc),
            }
        )

    return jsonify(_finalize_agent_turn(thread_id, state, before_count, student_id))


@app.route("/api/chat/<thread_id>/stream", methods=["POST"])
def api_stream_message(thread_id):
    """SSE agent run: streams live thought/action/observation traces, then final reply."""
    blocked, _bundle = _require_profile_ready_api()
    if blocked:
        return blocked

    data = request.json or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "empty"}), 400

    student_id = get_or_create_student()
    conversation_service.upsert_conversation(thread_id=thread_id, student_id=student_id)
    conversation_service.append_message(thread_id, "user", text)

    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    state = _prepare_agent_state(graph, config, student_id, text)
    before_count = len(state.get("messages") or [])

    def event_stream():
        yield _sse({"type": "status", "text": "Agent started — working through your request…"})
        final_state = state
        try:
            for mode, chunk in graph.stream(
                state, config=config, stream_mode=["custom", "values"]
            ):
                if mode == "custom" and isinstance(chunk, dict):
                    event_type = chunk.get("type") or "thought"
                    event_text = chunk.get("text") or ""
                    if event_text:
                        yield _sse({"type": event_type, "text": event_text})
                elif mode == "values" and isinstance(chunk, dict):
                    final_state = chunk
                    phase = chunk.get("current_phase")
                    if phase:
                        yield _sse({"type": "phase", "text": phase, "phase": phase})
            payload = _finalize_agent_turn(thread_id, final_state, before_count, student_id)
            payload["type"] = "done"
            yield _sse(payload)
        except Exception as exc:
            fallback = (
                "Sorry — I hit an error talking to the model. "
                "Please try again in a moment."
            )
            conversation_service.append_message(thread_id, "assistant", fallback)
            yield _sse(
                {
                    "type": "done",
                    "reply": fallback,
                    "replies": [fallback],
                    "recommendations": [],
                    "error_detail": str(exc),
                    "profile_complete": False,
                    "phase": "profiling",
                    "agent": {},
                }
            )

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _prepare_agent_state(graph, config, student_id: str, text: str) -> dict:
    snapshot = graph.get_state(config)
    if snapshot.values and snapshot.values.get("messages"):
        state = dict(snapshot.values)
    else:
        state = initial_state()
        saved = profile_service.get_saved_profile(student_id) or {}
        saved_profile = saved.get("profile") or {}
        if saved_profile:
            state["student_profile"] = {
                k: v for k, v in saved_profile.items() if v not in (None, "", [], {})
            }
    messages = list(state.get("messages") or [])
    messages.append({"role": "user", "content": text})
    state["messages"] = messages
    return state


def _finalize_agent_turn(thread_id: str, state: dict, before_count: int, student_id: str) -> dict:
    replies = _new_assistant_replies(before_count, state)
    if not replies:
        replies = [
            "I couldn't generate a reply just now. Could you try rephrasing that?"
        ]
    for reply in replies:
        conversation_service.append_message(thread_id, "assistant", reply)

    profile = state.get("student_profile") or {}
    from agent.state import REQUIRED_PROFILE_FIELDS

    missing = [f for f in REQUIRED_PROFILE_FIELDS if not profile.get(f)]
    recommendations = state.get("recommendations") or []
    if recommendations:
        recommendations_store.save_recommendations(student_id, recommendations)
    return {
        "reply": replies[-1],
        "replies": replies,
        "recommendations": recommendations,
        "profile_complete": bool(state.get("profile_complete")),
        "phase": state.get("current_phase") or "profiling",
        "agent": {
            "phase": state.get("current_phase") or "profiling",
            "profile_complete": bool(state.get("profile_complete")),
            "missing_fields": missing,
            "field_of_study": profile.get("field_of_study"),
            "degree_level": profile.get("degree_level"),
            "budget_pkr_per_semester": profile.get("budget_pkr_per_semester"),
        },
    }


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
