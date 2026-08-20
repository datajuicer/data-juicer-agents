# -*- coding: utf-8 -*-
"""Current-page context tool support for QA Copilot."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse


DEFAULT_PAGE_CONTEXT_MAX_CHARS = 6000
MAX_PAGE_CONTEXT_CHARS = 20000


def normalize_context_resources(resources: Any) -> List[Dict[str, Any]]:
    """Normalize request-level context resources into safe document resources."""
    if not isinstance(resources, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for index, resource in enumerate(resources):
        if not isinstance(resource, dict):
            continue

        text = resource.get("text")
        if not isinstance(text, str) or not text.strip():
            continue

        normalized.append(
            {
                "id": str(resource.get("id") or f"context_resource_{index}"),
                "type": str(resource.get("type") or "document"),
                "source": str(resource.get("source") or ""),
                "media_type": str(resource.get("media_type") or "text/plain"),
                "title": str(resource.get("title") or ""),
                "url": str(resource.get("url") or ""),
                "text": text,
                "char_count": _safe_int(resource.get("char_count"), len(text)),
                "truncated": bool(resource.get("truncated", False)),
                "extracted_at": str(resource.get("extracted_at") or ""),
            }
        )

    return normalized


def make_current_page_context_tool(resources: List[Dict[str, Any]]):
    """Create a request-local current page context tool."""
    page = _select_current_page(resources)

    def get_current_page_context(
        max_chars: int = DEFAULT_PAGE_CONTEXT_MAX_CHARS,
    ) -> ToolResponse:
        """Read the current documentation page context when needed."""
        if page is None:
            payload = {
                "available": False,
                "message": (
                    "No current page context resource was provided with this request."
                ),
            }
            return _tool_response(payload)

        bounded_max_chars = min(
            max(int(max_chars or 0), 500),
            MAX_PAGE_CONTEXT_CHARS,
        )
        text = page["text"]
        returned_text = text[:bounded_max_chars]
        payload = {
            "available": True,
            "resource_id": page["id"],
            "type": page["type"],
            "source": page["source"],
            "media_type": page["media_type"],
            "title": page["title"],
            "url": page["url"],
            "text": returned_text,
            "char_count": page["char_count"],
            "resource_truncated": page["truncated"],
            "tool_truncated": len(text) > len(returned_text),
            "extracted_at": page["extracted_at"],
        }
        return _tool_response(payload)

    return get_current_page_context


def _select_current_page(resources: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for resource in resources:
        if resource.get("id") == "current_page":
            return resource
    for resource in resources:
        if resource.get("type") == "document_page":
            return resource
    return resources[0] if resources else None


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _tool_response(payload: Dict[str, Any]) -> ToolResponse:
    return ToolResponse(
        content=[
            TextBlock(type="text", text=json.dumps(payload, ensure_ascii=False))
        ],
        metadata=payload,
    )


def is_web_docs_context_request(metadata: Any) -> bool:
    """Return True when the client explicitly exposes web docs page context."""
    if not isinstance(metadata, dict):
        return False

    client_environment = metadata.get("client_environment")
    page_context = metadata.get("page_context")
    if not isinstance(client_environment, dict) or not isinstance(page_context, dict):
        return False

    return (
        client_environment.get("surface") == "web_docs"
        and client_environment.get("supports_current_page_context") is True
        and page_context.get("available") is True
    )


CURRENT_PAGE_CONTEXT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_current_page_context",
        "description": (
            "Read the current documentation page context supplied with the "
            "request. Use this when the user asks about 'this page', the "
            "current page, selected text from the page, or page-local docs."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "max_chars": {
                    "type": "integer",
                    "description": (
                        "Maximum number of page text characters to return. "
                        "Defaults to 6000 and is capped at 20000."
                    ),
                    "default": DEFAULT_PAGE_CONTEXT_MAX_CHARS,
                    "minimum": 500,
                    "maximum": MAX_PAGE_CONTEXT_CHARS,
                }
            },
            "required": [],
        },
    },
}


def register_page_context_tool(
    toolkit,
    resources: List[Dict[str, Any]],
) -> None:
    """Register a request-local current-page context tool."""
    toolkit.register_tool_function(
        make_current_page_context_tool(resources),
        json_schema=CURRENT_PAGE_CONTEXT_SCHEMA,
    )


__all__ = [
    "normalize_context_resources",
    "is_web_docs_context_request",
    "register_page_context_tool",
]
