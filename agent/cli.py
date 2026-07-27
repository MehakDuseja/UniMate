"""Manual interactive test harness for the LangGraph agent.

No FastAPI/checkpointer yet, so this script owns the AgentState itself across
turns: append the user's message, call graph.invoke(state), print the newest
assistant message(s), repeat.

Usage: python3 -m agent.cli
"""
from __future__ import annotations

from .graph import build_graph
from .state import initial_state


def _new_assistant_messages(before_count: int, state) -> list[str]:
    texts = []
    for msg in state["messages"][before_count:]:
        if isinstance(msg, dict):
            if msg.get("role") == "assistant":
                texts.append(msg.get("content", ""))
        else:
            if getattr(msg, "type", "") == "ai":
                texts.append(getattr(msg, "content", ""))
    return texts


def main() -> None:
    graph = build_graph()
    state = initial_state()

    print("UniMate agent (Ctrl+C to quit)\n")
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
        state = graph.invoke(state)

        for text in _new_assistant_messages(before_count, state):
            print(f"\nAgent: {text}\n")


if __name__ == "__main__":
    main()
