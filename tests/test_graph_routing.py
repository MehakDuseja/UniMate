"""Tests for the pure routing functions in agent/graph.py - these decide
which node runs next and must route correctly without needing an actual
LLM call or graph execution."""
from __future__ import annotations

from agent.graph import _route_after_profile_builder, _route_after_refine, _route_entry


def test_route_entry_new_session_goes_to_profile_builder():
    assert _route_entry({"current_phase": "profiling", "profile_complete": False}) == "profile_builder"


def test_route_entry_mid_profiling_goes_to_profile_builder():
    assert _route_entry({"current_phase": "profiling", "profile_complete": False}) == "profile_builder"


def test_route_entry_after_presenting_goes_to_refine():
    assert _route_entry({"current_phase": "presenting", "profile_complete": True}) == "refine"


def test_route_entry_after_refining_goes_to_refine():
    assert _route_entry({"current_phase": "refining", "profile_complete": True}) == "refine"


def test_route_entry_presenting_without_complete_profile_goes_to_profile_builder():
    # Defensive case: phase says "presenting" but profile_complete somehow
    # isn't set - must not route into refine_node with no prior ranking.
    assert _route_entry({"current_phase": "presenting", "profile_complete": False}) == "profile_builder"


def test_route_after_profile_builder_to_retriever_when_complete():
    assert _route_after_profile_builder({"profile_complete": True}) == "retriever"


def test_route_after_profile_builder_to_end_when_incomplete():
    from langgraph.graph import END
    assert _route_after_profile_builder({"profile_complete": False}) == END


def test_route_after_refine_refine_action_goes_to_retriever():
    assert _route_after_refine({"refine_action": "refine"}) == "retriever"


def test_route_after_refine_answer_question_goes_to_qa():
    assert _route_after_refine({"refine_action": "answer_question"}) == "qa"


def test_route_after_refine_end_action_goes_to_end():
    from langgraph.graph import END
    assert _route_after_refine({"refine_action": "end"}) == END


def test_route_after_refine_unknown_action_defaults_to_end():
    from langgraph.graph import END
    assert _route_after_refine({"refine_action": None}) == END
