"""
Custom tool loader - dynamically loads tools from tool.json + main.py.
Scans the assets directory for custom tools and creates LangChain StructuredTool instances.
"""
import json
import os
import hashlib
import importlib.util
from typing import List, Dict, Optional
from dataclasses import dataclass

from langchain_core.tools import StructuredTool
from pydantic import create_model

from app.tools.registry import BUILTIN_TOOLS

CUSTOM_TOOLS_DIR = "/data/files"


@dataclass
class ToolManifest:
    name: str
    description: str
    parameters: dict
    source_path: str
    version: str = "1.0.0"
    requires_connections: list[str] | None = None


def load_tool_manifest(tool_dir: str) -> Optional[ToolManifest]:
    """Load tool.json from a tool directory."""
    json_path = os.path.join(tool_dir, "tool.json")
    if not os.path.exists(json_path):
        return None

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return ToolManifest(
            name=data["name"],
            description=data.get("description", ""),
            parameters=data.get("parameters", {}),
            source_path=os.path.join(tool_dir, "main.py"),
            version=data.get("version", "1.0.0"),
            requires_connections=data.get("requires_connections", None),
        )
    except (json.JSONDecodeError, KeyError):
        return None


def build_args_schema(params_schema: dict) -> type:
    """Build a Pydantic model from JSON Schema parameters."""
    if not params_schema or "properties" not in params_schema:
        from pydantic import BaseModel
        return BaseModel

    fields = {}
    props = params_schema.get("properties", {})
    required = params_schema.get("required", [])

    for name, prop in props.items():
        prop_type = _map_json_type(prop.get("type", "string"))
        description = prop.get("description", "")
        default = prop.get("default", ... if name in required else None)
        fields[name] = (prop_type, default, description)

    return create_model("ToolArgs", **fields) if fields else None


def _map_json_type(json_type: str):
    mapping = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    return mapping.get(json_type, str)


def load_custom_tool(manifest: ToolManifest) -> Optional[StructuredTool]:
    """Load a custom tool from its manifest and main.py."""
    if not os.path.exists(manifest.source_path):
        return None

    try:
        module_name = f"custom_tool_{manifest.name}"
        spec = importlib.util.spec_from_file_location(module_name, manifest.source_path)
        if spec is None or spec.loader is None:
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if not hasattr(module, "execute"):
            return None

        execute_func = module.execute
        args_schema = build_args_schema(manifest.parameters)

        tool = StructuredTool.from_function(
            func=execute_func,
            name=manifest.name,
            description=manifest.description,
            args_schema=args_schema,
        )
        return tool
    except Exception:
        return None


def discover_custom_tools(space_id: str = "") -> Dict[str, StructuredTool]:
    """Discover all custom tools for a space."""
    tools: Dict[str, StructuredTool] = {}
    tools_dir = os.path.join(CUSTOM_TOOLS_DIR, space_id, "tools") if space_id else CUSTOM_TOOLS_DIR

    if not os.path.isdir(tools_dir):
        return tools

    for entry in os.listdir(tools_dir):
        tool_dir = os.path.join(tools_dir, entry)
        if not os.path.isdir(tool_dir):
            continue

        manifest = load_tool_manifest(tool_dir)
        if manifest is None:
            continue

        if not os.path.isfile(manifest.source_path):
            continue

        cache_key = hashlib.md5(
            f"{manifest.source_path}_{os.path.getmtime(manifest.source_path)}".encode()
        ).hexdigest()

        tool = load_custom_tool(manifest)
        if tool is not None:
            tools[manifest.name] = tool

    return tools


def get_space_tools(space_id: str = "") -> List[StructuredTool]:
    """Get all tools (built-in + custom) for a space."""
    all_tools = list(BUILTIN_TOOLS.values())
    custom = discover_custom_tools(space_id)
    all_tools.extend(custom.values())
    return all_tools
