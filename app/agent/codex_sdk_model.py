"""PydanticAI FunctionModel backed by Codex SDK one-shot turns.

PydanticAI still owns structured output validation and retry behavior. This
module only replaces the provider transport: each model request starts a fresh
Codex SDK thread, runs one prompt, and returns the final text to PydanticAI.
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.agent.errors import ReasonerUnavailable
from app.core.config import settings


def build_codex_sdk_model() -> FunctionModel:
    return FunctionModel(
        _codex_request,
        model_name=f"codex-sdk:{settings.codex_model}",
    )


async def _codex_request(messages: list[ModelMessage], agent_info: AgentInfo) -> ModelResponse:
    prompt = _render_prompt(messages, agent_info)
    output_schema = None
    if agent_info.model_request_parameters.output_object is not None:
        output_schema = agent_info.model_request_parameters.output_object.json_schema

    try:
        from openai_codex import AsyncCodex, Sandbox

        async with AsyncCodex() as codex:
            thread = await codex.thread_start(
                model=settings.codex_model,
                sandbox=Sandbox.read_only,
                config={"model_reasoning_effort": settings.codex_model_reasoning_effort},
            )
            result = await thread.run(prompt, output_schema=output_schema)
    except Exception as exc:
        raise ReasonerUnavailable(f"Codex SDK 실행 실패: {exc}") from exc

    final_response = getattr(result, "final_response", None)
    if not final_response:
        raise ReasonerUnavailable("Codex SDK가 final_response를 반환하지 않았습니다.")

    return ModelResponse(
        parts=[TextPart(str(final_response))],
        model_name=f"codex-sdk:{settings.codex_model}",
        provider_name="codex-sdk",
        provider_details={"transport": "codex_sdk_one_shot"},
    )


def _render_prompt(messages: list[ModelMessage], agent_info: AgentInfo) -> str:
    sections: list[str] = []
    if agent_info.instructions:
        sections.append(f"[instructions]\n{agent_info.instructions}")

    if prompted := agent_info.model_request_parameters.prompted_output_instructions:
        sections.append(f"[structured_output_instructions]\n{prompted}")
    elif agent_info.model_request_parameters.output_object is not None:
        schema = agent_info.model_request_parameters.output_object.json_schema
        sections.append(
            "[structured_output_schema]\n"
            "Return only valid JSON matching this schema. Do not wrap it in markdown.\n"
            f"{json.dumps(schema, ensure_ascii=False, indent=2, default=str)}"
        )

    sections.append(f"[messages]\n{_messages_to_text(messages)}")
    return "\n\n".join(sections)


def _messages_to_text(messages: list[ModelMessage]) -> str:
    rendered: list[str] = []
    for message in messages:
        if isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, SystemPromptPart):
                    rendered.append(f"system: {part.content}")
                elif isinstance(part, UserPromptPart):
                    rendered.append(f"user: {_content_to_text(part.content)}")
                elif isinstance(part, ToolReturnPart):
                    rendered.append(f"tool_return: {part.model_response_str()}")
                else:
                    rendered.append(f"{part.part_kind}: {part!r}")
        elif isinstance(message, ModelResponse):
            text = message.text
            if text:
                rendered.append(f"assistant: {text}")
    return "\n\n".join(rendered)


def _content_to_text(content: str | Sequence[Any]) -> str:
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False, default=str)
