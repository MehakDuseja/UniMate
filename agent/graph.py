"""LangGraph state graph wiring.

Each user turn is one graph.invoke() call carrying the *full* prior state
(no checkpointer yet - that's added when this is wired into an API). Because
of that, the entry point has to be phase-aware: a message that arrives after
recommendations were already presented should re-enter at refine_node, not
restart profile_builder_node from scratch.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .nodes import presenter_node, profile_builder_node, ranker_node, refine_node, retriever_node
from .state import AgentState


def _route_entry(state: AgentState) -> str:
    phase = state.get("current_phase", "profiling")
    if phase in ("presenting", "refining") and state.get("profile_complete"):
        return "refine"
    return "profile_builder"


def _route_after_profile_builder(state: AgentState) -> str:
    return "retriever" if state.get("profile_complete") else END


def _route_after_refine(state: AgentState) -> str:
    return "retriever" if state.get("refine_action") == "refine" else END


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("profile_builder", profile_builder_node)
    graph.add_node("retriever", retriever_node)
    graph.add_node("ranker", ranker_node)
    graph.add_node("presenter", presenter_node)
    graph.add_node("refine", refine_node)

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
        "refine", _route_after_refine, {"retriever": "retriever", END: END}
    )

    return graph.compile()
