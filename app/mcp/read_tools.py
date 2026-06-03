"""Scoped read-tool registry for the JB WM MCP server."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlmodel import Session

from app.models.agent import AgentEvent
from app.tools import data_tools
from app.tools.policy_tools import search_policy_documents


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


TOOL_SPECS: dict[str, dict[str, Any]] = {
    "get_customer_profile": {
        "description": "Read the scoped customer's profile.",
        "inputSchema": _schema({}),
    },
    "get_health_data": {
        "description": "Read consented health data and health events for the scoped customer.",
        "inputSchema": _schema({}),
    },
    "get_portfolio_summary": {
        "description": "Read portfolio allocation and risk summary for the scoped customer.",
        "inputSchema": _schema({}),
    },
    "get_asset_events": {
        "description": "Read asset events for the scoped customer.",
        "inputSchema": _schema({}),
    },
    "get_insurance_summary": {
        "description": "Read insurance coverage summary for the scoped customer.",
        "inputSchema": _schema({}),
    },
    "get_loan_status": {
        "description": "Read loan status for the scoped customer.",
        "inputSchema": _schema({}),
    },
    "get_account_balances": {
        "description": "Read account balances and liquidity summary for the scoped customer.",
        "inputSchema": _schema({}),
    },
    "get_account_transactions": {
        "description": "Read recent normalized account transactions for the scoped customer.",
        "inputSchema": _schema({}),
    },
    "get_card_bills": {
        "description": "Read card bill summaries for the scoped customer.",
        "inputSchema": _schema({}),
    },
    "get_loan_switch_precheck": {
        "description": "Read loan-switch precheck mock result for the scoped customer.",
        "inputSchema": _schema(
            {
                "loan_id": {"type": "string"},
            }
        ),
    },
    "get_customer_memory": {
        "description": "Read long-term personalization memory for the scoped customer.",
        "inputSchema": _schema({}),
    },
    "get_population_stat": {
        "description": "Read a population statistic by metric. Defaults age_band to scoped customer profile.",
        "inputSchema": _schema(
            {
                "metric": {"type": "string"},
                "age_band": {"type": "string"},
            },
            required=["metric"],
        ),
    },
    "search_policy_documents": {
        "description": "Search static read-only policy documents.",
        "inputSchema": _schema(
            {
                "query": {"type": "string"},
                "doc_type": {"type": "string"},
            },
            required=["query"],
        ),
    },
}


def list_read_tools() -> list[dict[str, Any]]:
    return [{"name": name, **spec} for name, spec in TOOL_SPECS.items()]


def call_read_tool(
    db: Session,
    *,
    session_id: str | None,
    customer_id: str,
    name: str,
    arguments: dict[str, Any] | None = None,
) -> Any:
    if name not in TOOL_SPECS:
        raise ValueError(f"Unknown MCP read tool: {name}")

    args = dict(arguments or {})
    args.pop("customer_id", None)  # scope is server-side, never model-controlled

    handlers: dict[str, Callable[[], Any]] = {
        "get_customer_profile": lambda: data_tools.get_customer_profile(db, customer_id),
        "get_health_data": lambda: data_tools.get_health_data(db, customer_id),
        "get_portfolio_summary": lambda: data_tools.get_portfolio_summary(db, customer_id),
        "get_asset_events": lambda: data_tools.get_asset_events(db, customer_id),
        "get_insurance_summary": lambda: data_tools.get_insurance_summary(db, customer_id),
        "get_loan_status": lambda: data_tools.get_loan_status(db, customer_id),
        "get_account_balances": lambda: data_tools.get_account_balances(db, customer_id),
        "get_account_transactions": lambda: data_tools.get_account_transactions(db, customer_id),
        "get_card_bills": lambda: data_tools.get_card_bills(db, customer_id),
        "get_loan_switch_precheck": lambda: data_tools.get_loan_switch_precheck(
            db,
            customer_id,
            loan_id=args.get("loan_id"),
        ),
        "get_customer_memory": lambda: data_tools.get_customer_memory(db, customer_id),
        "get_population_stat": lambda: _get_population_stat(db, customer_id, args),
        "search_policy_documents": lambda: search_policy_documents(
            query=str(args.get("query", "")),
            doc_type=args.get("doc_type"),
        ),
    }
    result = handlers[name]()
    _audit_tool_call(db, session_id=session_id, name=name, arguments=args)
    return result


def _get_population_stat(db: Session, customer_id: str, args: dict[str, Any]) -> dict:
    age_band = args.get("age_band")
    if not age_band:
        age_band = data_tools.get_customer_profile(db, customer_id).get("age_band", "")
    return data_tools.get_population_stat(db, str(age_band), str(args["metric"]))


def _audit_tool_call(
    db: Session,
    *,
    session_id: str | None,
    name: str,
    arguments: dict[str, Any],
) -> None:
    if not session_id:
        return
    db.add(
        AgentEvent(
            session_id=session_id,
            type="tool_call",
            detail={"via": "mcp", "tool": name, "arguments": arguments},
        )
    )
    db.commit()
