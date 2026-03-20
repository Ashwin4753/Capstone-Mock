from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except Exception:  # pragma: no cover
    ClientSession = None
    StdioServerParameters = None
    stdio_client = None


class FigmaMCPClient:
    """
    Optional frontend token provider.

    This client should never be a hard blocker for full-stack modernization runs.
    """

    def __init__(
        self,
        *,
        server_command: str = "npx",
        server_args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        self.server_command = server_command
        self.server_args = server_args or ["-y", "figma-developer-mcp", "--stdio"]
        self.env = env or os.environ.copy()

    def is_available(self) -> bool:
        return (
            ClientSession is not None
            and StdioServerParameters is not None
            and stdio_client is not None
            and bool(self.env.get("FIGMA_API_KEY"))
        )

    async def health_check(self) -> Dict[str, Any]:
        if not self.is_available():
            return {
                "ok": False,
                "reason": "Figma MCP dependencies or FIGMA_API_KEY missing",
            }

        try:
            tools = await self.list_tools()
            return {"ok": True, "tool_count": len(tools), "tools": tools}
        except Exception as exc:
            return {"ok": False, "reason": str(exc)}

    async def list_tools(self) -> List[str]:
        async with self._session() as session:
            response = await session.list_tools()
            return [tool.name for tool in getattr(response, "tools", [])]

    async def fetch_tokens(self, file_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Best-effort token fetch + normalization.
        Returns a flattened token map when possible.
        """
        if not self.is_available():
            return {}

        tool_names = await self.list_tools()

        preferred_tools = [
            "get_design_tokens",
            "get_local_variables",
            "get_file_variables",
            "get_file_styles",
        ]
        tool_name = next((name for name in preferred_tools if name in tool_names), None)
        if not tool_name:
            return {}

        payload_candidates = []
        if file_key:
            payload_candidates.extend(
                [
                    {"fileKey": file_key},
                    {"file_key": file_key},
                    {"key": file_key},
                ]
            )
        payload_candidates.append({})

        async with self._session() as session:
            last_error: Optional[Exception] = None
            for payload in payload_candidates:
                try:
                    response = await session.call_tool(tool_name, payload)
                    content = self._extract_tool_content(response)
                    parsed = self._parse_json_like(content)
                    return self._flatten_tokens(parsed)
                except Exception as exc:
                    last_error = exc
                    continue

        if last_error:
            raise last_error
        return {}

    def _extract_tool_content(self, response: Any) -> Any:
        content = getattr(response, "content", None)
        if not content:
            return {}

        if isinstance(content, list):
            texts = []
            for item in content:
                text = getattr(item, "text", None)
                if text:
                    texts.append(text)
            if len(texts) == 1:
                return texts[0]
            if texts:
                return "\n".join(texts)
        return content

    def _parse_json_like(self, raw: Any) -> Any:
        if isinstance(raw, (dict, list)):
            return raw
        if not isinstance(raw, str):
            return {}

        text = raw.strip()
        if not text:
            return {}

        try:
            return json.loads(text)
        except Exception:
            return {"raw": text}

    def _flatten_tokens(self, payload: Any) -> Dict[str, Any]:
        flat: Dict[str, Any] = {}

        def walk(prefix: str, value: Any) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    next_prefix = f"{prefix}.{key}" if prefix else str(key)
                    walk(next_prefix, child)
            elif isinstance(value, list):
                for idx, child in enumerate(value):
                    next_prefix = f"{prefix}[{idx}]"
                    walk(next_prefix, child)
            else:
                if prefix:
                    flat[prefix] = value

        if isinstance(payload, dict):
            walk("", payload)
            return flat

        return {}

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _session(self):
        if not self.is_available():
            raise RuntimeError("Figma MCP client unavailable")

        server_params = StdioServerParameters(
            command=self.server_command,
            args=self.server_args,
            env=self.env,
        )

        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session