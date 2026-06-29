"""
Memory types and YAML frontmatter parser.
Inspired by claude-code's memory system: file-based, visible, editable.
Four memory types: user, feedback, project, reference.
"""
import yaml
import re
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone

MEMORY_TYPE_VALUES = ("user", "feedback", "project", "reference")


@dataclass
class MemoryEntry:
    name: str
    description: str
    mem_type: str  # user, feedback, project, reference
    content: str = ""
    file_path: str = ""
    updated: str = ""

    def to_markdown(self) -> str:
        now = datetime.now(timezone.utc).isoformat()
        updated = self.updated or now
        return f"""---
name: {self.name}
description: {self.description}
type: {self.mem_type}
updated: {updated}
---

{self.content.strip()}
"""


@dataclass
class MemoryIndexEntry:
    title: str
    file_name: str
    description: str
    mem_type: str = ""


def parse_frontmatter(content: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """Split YAML frontmatter from Markdown body."""
    pattern = r'^---\s*\n(.*?)\n---\s*\n'
    match = re.match(pattern, content, re.DOTALL)
    if not match:
        return None, content
    try:
        metadata = yaml.safe_load(match.group(1))
        if not isinstance(metadata, dict):
            return None, content
        body = content[match.end():]
        return metadata, body
    except Exception:
        return None, content


def parse_memory_file(content: str, file_path: str = "") -> Optional[MemoryEntry]:
    """Parse a memory .md file into a MemoryEntry."""
    frontmatter, body = parse_frontmatter(content)
    if frontmatter is None:
        return None

    mem_type = frontmatter.get("type", "project")
    if mem_type not in MEMORY_TYPE_VALUES:
        mem_type = "project"

    return MemoryEntry(
        name=frontmatter.get("name", ""),
        description=frontmatter.get("description", ""),
        mem_type=mem_type,
        content=body.strip(),
        file_path=file_path,
        updated=frontmatter.get("updated", ""),
    )
