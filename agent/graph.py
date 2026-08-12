"""LangGraph state graph wiring.

Each user turn is one graph.invoke() call carrying the full state for a given
thread_id. The entry point is phase-aware: a message that arrives after
recommendations were already presented should re-enter at refine_node, not
restart profile_builder_node from scratch.

A SqliteSaver checkpointer makes conversations durable across process
restarts (see build_graph() below) - callers still pass the full state as
they always have (this project's callers, agent/cli.py and web_app/app.py,
own state explicitly rather than relying on LangGraph to reload it), but the
checkpointer additionally persists it under a thread_id, so a new process can
recover a conversation via `graph.get_state(config)` instead of only ever
starting from initial_state().
"""
from __future__ import annotations

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from src.config import AGENT_CHECKPOINT_DB

from .nodes import presenter_node, profile_builder_node, qa_node, ranker_node, refine_node, retriever_node
from .state import AgentState


def _route_entry(state: AgentState) -> str:
    phase = state.get("current_phase", "profiling")
    if phase in ("presenting", "refining") and state.get("profile_complete"):
        return "refine"
    return "profile_builder"


def _route_after_profile_builder(state: AgentState) -> str:
    return "retriever" if state.get("profile_complete") else END


def _route_after_refine(state: AgentState) -> str:
    action = state.get("refine_action")
    if action == "refine":
        return "retriever"
    if action == "answer_question":
        return "qa"
    # "chitchat" and "end" both reply straight from refine_node itself, no
    # retrieval or ranking needed - see refine_node.
    return END


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("profile_builder", profile_builder_node)
    graph.add_node("retriever", retriever_node)
    graph.add_node("ranker", ranker_node)
    graph.add_node("presenter", presenter_node)
    graph.add_node("refine", refine_node)
    graph.add_node("qa", qa_node)

    graph.add_conditional_edges(
        START, _route_entry, {"profile_builder": "profile_builder", "refine": "refine"}
    )
    graph.add_conditional_edges(
        "profile_builder", _route_after_profile_builder, {"retriever": "retriever", END: END}
    )
    graph.add_edge("retriever", "ranker")
    graph.add_edge("ranker", "presenter")
    graph.add_edge("presenter", END)
    graph.add_conditional_edges(
        "refine", _route_after_refine, {"retriever": "retriever", "qa": "qa", END: END}
    )
    graph.add_edge("qa", END)

    # check_same_thread=False: this connection is opened once (build_graph()
    # is typically called once and cached in web_app/app.py) and then reused
    # across every subsequent turn/thread, which a server framework may
    # dispatch from different worker threads.
    AGENT_CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(AGENT_CHECKPOINT_DB), check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    return graph.compile(checkpointer=checkpointer)
