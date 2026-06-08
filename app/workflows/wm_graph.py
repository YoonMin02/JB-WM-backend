"""LangGraph assembly for JB-WM workflow state management."""
from __future__ import annotations

from functools import lru_cache

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.workflows import nodes
from app.workflows.state import WMGraphState


@lru_cache
def get_workflow_graph():
    """Compile the local LangGraph workflow.

    Local development uses `InMemorySaver`. Production should replace the
    checkpointer with durable storage, but authorization must still happen
    before calling this graph with a thread id.
    """

    graph = StateGraph(WMGraphState)
    graph.add_node("data_refresh", nodes.data_refresh)
    graph.add_node("signal_detect", nodes.signal_detect)
    graph.add_node("signal_gate", nodes.signal_gate)
    graph.add_node("build_context", nodes.build_context)
    graph.add_node("spawn_agent", nodes.spawn_agent)
    graph.add_node("validate_output", nodes.validate_output)
    graph.add_node("policy_check", nodes.policy_check)
    graph.add_node("approval_interrupt", nodes.approval_interrupt)
    graph.add_node("execute_action", nodes.execute_action)
    graph.add_node("verify_result", nodes.verify_result)
    graph.add_node("update_memory", nodes.update_memory)

    graph.add_edge(START, "data_refresh")
    graph.add_edge("data_refresh", "signal_detect")
    graph.add_edge("signal_detect", "signal_gate")
    graph.add_edge("signal_gate", "build_context")
    graph.add_edge("build_context", "spawn_agent")
    graph.add_edge("spawn_agent", "validate_output")
    graph.add_edge("validate_output", "policy_check")
    graph.add_conditional_edges(
        "policy_check",
        nodes.route_after_policy,
        {"approval_interrupt": "approval_interrupt", "verify_result": "verify_result"},
    )
    graph.add_edge("approval_interrupt", "execute_action")
    graph.add_conditional_edges(
        "execute_action",
        nodes.route_after_execution,
        {"approval_interrupt": "approval_interrupt", "verify_result": "verify_result"},
    )
    graph.add_edge("verify_result", "update_memory")
    graph.add_edge("update_memory", END)
    return graph.compile(checkpointer=InMemorySaver())
