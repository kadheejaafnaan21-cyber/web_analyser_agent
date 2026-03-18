"""
agent/graph.py
──────────────
Defines and compiles the LangGraph StateGraph.

This is the "brain" of the system — it wires all the nodes together and
defines WHEN each node runs (conditional edges).

Graph structure:

  START
    │
    ▼
  parse_intent  ← reads user message, extracts intent + URL
    │
    ├─[has URL?]──────────────────────────────────────────┐
    │                                                      ▼
    │                                               fetch_website
    │                                                      │
    │                                    ┌─────────────────┼─────────────────┐
    │                                    ▼                 ▼                 ▼
    │                             seo_analysis   accessibility_analysis  content_analysis
    │                                    │                 │                 │
    │                                    └─────────────────┼─────────────────┘
    │                                                      ▼
    └─[DB-only intent]──────────────────► execute_db_operation
                                                      │
                                                      ▼
                                               format_response
                                                      │
                                                     END

Beginner tip: "Conditional edges" = the graph decides which node to visit next
based on the current state (like an if/else in code, but for graph routing).
"""

from langgraph.graph import StateGraph, END

from agent.state import AgentState
from agent.nodes import (
    parse_intent,
    fetch_website,
    run_seo_analysis,
    run_accessibility_analysis,
    run_content_analysis,
    execute_db_operation,
    format_response,
)
from utils.logger import get_logger

logger = get_logger(__name__)


# ── Routing functions ─────────────────────────────────────────────────────────
# These functions look at the state and return the name of the NEXT node.

def route_after_intent(state: AgentState) -> str:
    """
    After parsing intent, decide whether to fetch a website
    or go straight to a DB operation.
    """
    intent = state.get("intent", "unknown")
    url    = state.get("target_url")

    if intent == "analyze_website" and url:
        logger.info("[router] → fetch_website")
        return "fetch_website"

    elif intent in ("list_sites", "list_reports", "db_query",
                    "delete_old_reports", "update_score", "show_logs"):
        logger.info("[router] → execute_db_operation")
        return "execute_db_operation"

    else:
        # Unknown intent — skip to formatting a "I don't understand" response
        logger.info("[router] → format_response (unknown intent)")
        return "format_response"


def route_after_fetch(state: AgentState) -> list[str]:
    """
    After fetching the website, run all three analyses IN PARALLEL.
    LangGraph supports fan-out — returning a list of node names.
    """
    if state.get("fetch_error"):
        # Fetch failed — skip analysis, go straight to format
        logger.warning("[router] fetch failed → format_response")
        return ["format_response"]

    logger.info("[router] → [seo, accessibility, content] (parallel)")
    return ["run_seo_analysis", "run_accessibility_analysis", "run_content_analysis"]


# ── Build the graph ───────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Assemble and compile the LangGraph workflow.

    Steps:
      1. Create a StateGraph (typed with AgentState)
      2. Add every node (node_name, function)
      3. Set the entry point (first node to run)
      4. Add edges (node_A → node_B, or conditional)
      5. Compile and return
    """
    # ── 1. Create the graph ────────────────────────────────────────────────
    graph = StateGraph(AgentState)

    # ── 2. Register nodes ─────────────────────────────────────────────────
    graph.add_node("parse_intent",              parse_intent)
    graph.add_node("fetch_website",             fetch_website)
    graph.add_node("run_seo_analysis",          run_seo_analysis)
    graph.add_node("run_accessibility_analysis",run_accessibility_analysis)
    graph.add_node("run_content_analysis",      run_content_analysis)
    graph.add_node("execute_db_operation",      execute_db_operation)
    graph.add_node("format_response",           format_response)

    # ── 3. Entry point ────────────────────────────────────────────────────
    graph.set_entry_point("parse_intent")

    # ── 4. Edges ──────────────────────────────────────────────────────────

    # After parsing intent, route dynamically
    graph.add_conditional_edges(
        "parse_intent",
        route_after_intent,
        {
            "fetch_website":         "fetch_website",
            "execute_db_operation":  "execute_db_operation",
            "format_response":       "format_response",
        },
    )

    # After fetching, fan-out to all three analyses (or bail to format)
    graph.add_conditional_edges(
        "fetch_website",
        route_after_fetch,
        {
            "run_seo_analysis":           "run_seo_analysis",
            "run_accessibility_analysis": "run_accessibility_analysis",
            "run_content_analysis":       "run_content_analysis",
            "format_response":            "format_response",
        },
    )

    # All three analyses converge at execute_db_operation
    graph.add_edge("run_seo_analysis",           "execute_db_operation")
    graph.add_edge("run_accessibility_analysis",  "execute_db_operation")
    graph.add_edge("run_content_analysis",        "execute_db_operation")

    # DB operation always flows to format_response
    graph.add_edge("execute_db_operation", "format_response")

    # format_response is the terminal node
    graph.add_edge("format_response", END)

    # ── 5. Compile ────────────────────────────────────────────────────────
    compiled = graph.compile()
    logger.info("✅ LangGraph compiled successfully.")
    return compiled


# ── Singleton: compile once at import time ────────────────────────────────────
agent_graph = build_graph()