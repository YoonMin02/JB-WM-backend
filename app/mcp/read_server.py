"""Minimal stdio MCP server for read-only JB WM tools.

The server is launched per Codex thread with `JBWM_MCP_CUSTOMER_ID` and optional
`JBWM_MCP_SESSION_ID`. It exposes only scoped read tools and writes tool-call audit
events when a session id is available.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

from sqlmodel import Session

from app.core.database import engine
from app.mcp.read_tools import call_read_tool, list_read_tools


def _response(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _handle(message: dict[str, Any]) -> dict[str, Any] | None:
    request_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}

    if request_id is None:
        return None
    if method == "initialize":
        return _response(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "jbwm-read-tools", "version": "0.1.0"},
            },
        )
    if method == "tools/list":
        return _response(request_id, {"tools": list_read_tools()})
    if method == "tools/call":
        customer_id = os.environ.get("JBWM_MCP_CUSTOMER_ID", "")
        if not customer_id:
            return _error(request_id, -32000, "JBWM_MCP_CUSTOMER_ID is required")
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            with Session(engine) as db:
                result = call_read_tool(
                    db,
                    session_id=os.environ.get("JBWM_MCP_SESSION_ID"),
                    customer_id=customer_id,
                    name=str(name),
                    arguments=arguments,
                )
        except Exception as exc:
            return _error(request_id, -32001, str(exc))
        return _response(
            request_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, default=str),
                    }
                ]
            },
        )
    return _error(request_id, -32601, f"Method not found: {method}")


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            response = _handle(message)
        except Exception as exc:
            response = _error(None, -32700, str(exc))
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
