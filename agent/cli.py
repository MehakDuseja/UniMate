"""Manual interactive test harness for the LangGraph agent.

Usage: python3 -m agent.cli [thread_id]

Conversations are durable across process restarts (agent/graph.py wires in a
SqliteSaver checkpointer) - running with the same thread_id (the default,
"cli-default", if none is given) resumes where a previous run left off
instead of starting over. This script still owns/appends to the state dict
itself each turn (same as before), the checkpointer just means a NEW process
can pick that state back up via graph.get_state() instead of only ever
starting from initial_state().
"""
from __future__ import annotations

import sys

from .graph import build_graph
from .state import initial_state


def _role_and_content(msg) -> tuple[str, str]:
    if isinstance(msg, dict):
        return msg.get("role", ""), msg.get("content", "")
    role = "user" if getattr(msg, "type", "") == "human" else "assistant"
    return role, getattr(msg, "content", "")


def _new_assistant_messages(before_count: int, state) -> list[str]:
    texts = []
    for msg in state["messages"][before_count:]:
        role, content = _role_and_content(msg)
        if role == "assistant":
            texts.append(content)
    return texts


def main() -> None:
    thread_id = sys.argv[1] if len(sys.argv) > 1 else "cli-default"
    config = {"configurable": {"thread_id": thread_id}}

    graph = build_graph()
    snapshot = graph.get_state(config)

    if snapshot.values.get("messages"):
        state = snapshot.values
        print(f"UniMate agent (Ctrl+C to quit) - resuming thread '{thread_id}'\n")
        for msg in state["messages"]:
            role, content = _role_and_content(msg)
            print(f"{'You' if role == 'user' else 'Agent'}: {content}\n")
    else:
        state = initial_state()
        print(f"UniMate agent (Ctrl+C to quit) - new thread '{thread_id}'\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break
        if not user_input:
            continue

        state["messages"].append({"role": "user", "content": user_input})
        before_count = len(state["messages"])
        state = graph.invoke(state, config=config)

        for text in _new_assistant_messages(before_count, state):
            print(f"\nAgent: {text}\n")


if __name__ == "__main__":
    main()
