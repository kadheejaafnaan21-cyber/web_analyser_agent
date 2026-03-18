"""
agent/state.py
──────────────
Defines the AgentState TypedDict — the "shared memory" that flows between
every node in the LangGraph graph.

Beginner tip: Think of AgentState as a bucket that gets passed from node
to node. Each node can read from it and write new values to it. By the end
of the graph, the bucket contains everything the agent learned and did.

TypedDict = a Python dict with type hints so your editor can autocomplete.
"""

from typing import TypedDict, Annotated
from operator import add   # Used by LangGraph to merge list fields


class AgentState(TypedDict):
    """
    Shared state passed through every node in the LangGraph graph.

    Convention:
      - Fields ending in _result store analysis output dicts.
      - Fields ending in _error store error strings (or None).
      - messages accumulates the conversation history.
    """

    # ── Conversation ──────────────────────────────────────────────────────────
    # Annotated[list, add] tells LangGraph: when merging states, ADD to this
    # list rather than replacing it. This lets us accumulate messages.
    messages: Annotated[list, add]

    # ── User intent (parsed by the first node) ────────────────────────────────
    user_input: str            # The raw text the user typed
    intent: str                # e.g. "analyze_website", "db_query", "delete_old"
    target_url: str | None     # URL extracted from user message (if any)
    db_action: str | None      # e.g. "save", "list", "delete_old", "update_score"
    db_params: dict | None     # Extra parameters for DB actions

    # ── Website fetch ─────────────────────────────────────────────────────────
    fetch_error: str | None    # Set if the page could not be fetched

    # ── Analysis results ──────────────────────────────────────────────────────
    seo_result: dict | None
    accessibility_result: dict | None
    content_result: dict | None

    # ── Database results ──────────────────────────────────────────────────────
    db_result: dict | None     # What the DB operation returned
    db_error: str | None       # Set if a DB operation failed

    # ── Final formatted response sent to the user ─────────────────────────────
    final_response: str