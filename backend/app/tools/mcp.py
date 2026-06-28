"""
MCP (Model Context Protocol) integration module.
Supports STDIO and SSE transport modes for connecting external tool servers.
"""
import json
import os
import asyncio
import subprocess
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from pydantic import BaseModel
from langchain_core.tools import BaseTool, tool


@dataclass
class MCPServerConfig:
    name: str
    transport: str  # "stdio" or "sse"
    command: str = ""
    args: List[str] = field(default_factory=list)
    url: str = ""
    env: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True


def parse_mcp_config(config_dict: dict) -> Optional[MCPServerConfig]:
    """Parse an mcp.json dict into MCPServerConfig."""
    try:
        name = config_dict.get("name", config_dict.get("slug", "unnamed"))
        transport = config_dict.get("transport", config_dict.get("type", "stdio"))

        cfg = MCPServerConfig(
            name=name,
            transport=transport,
            command=config_dict.get("command", config_dict.get("cmd", "")),
            args=config_dict.get("args", []),
            url=config_dict.get("url", config_dict.get("endpoint", "")),
            env=config_dict.get("env", {}),
            enabled=config_dict.get("enabled", True),
        )
        return cfg
    except Exception:
        return None


def resolve_env_vars(env: Dict[str, str]) -> Dict[str, str]:
    """Resolve ${connections.xxx.yyy} placeholders in env values."""
    import re
    resolved = {}
    for key, value in env.items():
        def replacer(match):
            slug = match.group(1)
            field = match.group(2)
            env_key = f"CVO_CONN_{slug.upper()}_{field.upper()}"
            return os.environ.get(env_key, "")
        resolved[key] = re.sub(r'\$\{connections\.(\w+)\.(\w+)\}', replacer, value)
    return resolved


async def discover_mcp_tools(config: MCPServerConfig) -> List[BaseTool]:
    """Connect to an MCP server and discover available tools."""
    if not config.enabled:
        return []

    if config.transport == "stdio":
        return await _discover_stdio_tools(config)
    elif config.transport == "sse":
        return await _discover_sse_tools(config)
    return []


async def _discover_stdio_tools(config: MCPServerConfig) -> List[BaseTool]:
    """Discover tools from a STDIO MCP server."""
    try:
        resolved_env = {**os.environ.copy(), **resolve_env_vars(config.env)}

        proc = await asyncio.create_subprocess_exec(
            config.command, *config.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=resolved_env,
        )

        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }
        payload = json.dumps(init_request) + "\n"

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(payload.encode("utf-8")),
            timeout=15,
        )

        proc.terminate()
        await proc.wait()

        if stderr:
            pass

        lines = stdout.decode("utf-8", errors="replace").strip().split("\n")
        tools: List[BaseTool] = []

        for line in lines:
            try:
                response = json.loads(line)
                if "result" in response and "tools" in response["result"]:
                    for tool_data in response["result"]["tools"]:
                        t = _mcp_tool_to_langchain(tool_data)
                        if t:
                            tools.append(t)
            except json.JSONDecodeError:
                continue

        return tools
    except Exception:
        return []


async def _discover_sse_tools(config: MCPServerConfig) -> List[BaseTool]:
    """Discover tools from an SSE MCP server."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                config.url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            tools: List[BaseTool] = []
            if "result" in data and "tools" in data["result"]:
                for tool_data in data["result"]["tools"]:
                    t = _mcp_tool_to_langchain(tool_data)
                    if t:
                        tools.append(t)
            return tools
    except Exception:
        return []


def _mcp_tool_to_langchain(tool_data: dict) -> Optional[BaseTool]:
    """Convert an MCP tool definition to a LangChain BaseTool."""
    try:
        name = tool_data.get("name", "unknown")
        description = tool_data.get("description", "")
        input_schema = tool_data.get("inputSchema", {})

        @tool(name, description=description)
        def mcp_tool_stub(**kwargs) -> str:
            return json.dumps(kwargs)

        return mcp_tool_stub
    except Exception:
        return None


def load_mcp_configs_from_dir(mcp_dir: str) -> List[MCPServerConfig]:
    """Load MCP configurations from a directory of mcp.json files."""
    configs = []
    if not os.path.isdir(mcp_dir):
        return configs

    for entry in os.listdir(mcp_dir):
        json_path = os.path.join(mcp_dir, entry, "mcp.json") if os.path.isdir(os.path.join(mcp_dir, entry)) else os.path.join(mcp_dir, entry) if entry.endswith(".json") else ""

        if not json_path or not os.path.isfile(json_path):
            config_path = os.path.join(mcp_dir, entry)
            if os.path.isdir(config_path):
                json_path = os.path.join(config_path, "mcp.json")

        if not os.path.isfile(json_path):
            continue

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                for item in data:
                    cfg = parse_mcp_config(item)
                    if cfg:
                        configs.append(cfg)
            else:
                cfg = parse_mcp_config(data)
                if cfg:
                    configs.append(cfg)
        except Exception:
            continue

    return configs


async def discover_all_mcp_tools(space_id: str = "") -> List[BaseTool]:
    """Discover all MCP tools for a space."""
    mcp_dir = os.path.join("/data/files", space_id, "mcp") if space_id else "/data/files/mcp"
    configs = load_mcp_configs_from_dir(mcp_dir)

    tasks = [discover_mcp_tools(cfg) for cfg in configs]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_tools = []
    for result in results:
        if isinstance(result, list):
            all_tools.extend(result)

    return all_tools
