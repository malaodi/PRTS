"""
Memory file manager — reads/writes memory files and maintains MEMORY.md index.
All memories are stored as visible, editable .md files with YAML frontmatter.
"""
import os
import re
from typing import List, Optional
from dataclasses import dataclass

from app.memories.types import MemoryEntry, MemoryIndexEntry, parse_memory_file, parse_frontmatter

MEMORY_BASE = "/data/files"
ENTRYPOINT_NAME = "MEMORY.md"
MAX_ENTRYPOINT_LINES = 200
MAX_ENTRYPOINT_BYTES = 25000


def get_memory_dir(space_id: str) -> str:
    return os.path.join(MEMORY_BASE, space_id, "memory")


def get_entrypoint_path(space_id: str) -> str:
    return os.path.join(get_memory_dir(space_id), ENTRYPOINT_NAME)


def ensure_memory_dir(space_id: str):
    os.makedirs(get_memory_dir(space_id), exist_ok=True)


def read_entrypoint(space_id: str) -> List[MemoryIndexEntry]:
    """Read MEMORY.md and parse the index entries."""
    path = get_entrypoint_path(space_id)
    if not os.path.isfile(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return []

    entries = []
    pattern = r'^- \[(.+?)\]\((.+?)\)\s*[-—]\s*(.+)$'
    for line in content.split("\n"):
        match = re.match(pattern, line.strip())
        if match:
            entries.append(MemoryIndexEntry(
                title=match.group(1),
                file_name=match.group(2),
                description=match.group(3),
            ))
    return entries


def write_entrypoint(space_id: str, entries: List[MemoryIndexEntry]):
    """Write or update MEMORY.md index."""
    path = get_entrypoint_path(space_id)
    ensure_memory_dir(space_id)

    lines = ["# Memory Index\n"]
    for e in entries:
        lines.append(f"- [{e.title}]({e.file_name}) — {e.description}")

    content = "\n".join(lines)
    lines_list = content.split("\n")

    if len(lines_list) > MAX_ENTRYPOINT_LINES:
        content = "\n".join(lines_list[:MAX_ENTRYPOINT_LINES])

    if len(content.encode("utf-8")) > MAX_ENTRYPOINT_BYTES:
        truncated = content[:MAX_ENTRYPOINT_BYTES // 2]
        content = truncated

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def read_memory(space_id: str, file_name: str) -> Optional[MemoryEntry]:
    """Read a single memory file."""
    path = os.path.join(get_memory_dir(space_id), file_name)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return parse_memory_file(content, file_path=path)
    except Exception:
        return None


def write_memory(space_id: str, entry: MemoryEntry):
    """Write a memory file and update MEMORY.md index."""
    ensure_memory_dir(space_id)
    file_name = f"{entry.mem_type}_{_sanitize_filename(entry.name)}.md"
    path = os.path.join(get_memory_dir(space_id), file_name)

    with open(path, "w", encoding="utf-8") as f:
        f.write(entry.to_markdown())

    entries = read_entrypoint(space_id)
    existing = [e for e in entries if e.file_name != file_name]

    existing.append(MemoryIndexEntry(
        title=entry.name,
        file_name=file_name,
        description=entry.description,
        mem_type=entry.mem_type,
    ))

    write_entrypoint(space_id, existing)
    return file_name


def delete_memory(space_id: str, file_name: str) -> bool:
    """Delete a memory file and remove from MEMORY.md."""
    path = os.path.join(get_memory_dir(space_id), file_name)
    if os.path.isfile(path):
        os.remove(path)

    entries = read_entrypoint(space_id)
    entries = [e for e in entries if e.file_name != file_name]
    write_entrypoint(space_id, entries)
    return True


def scan_memories(space_id: str) -> List[MemoryEntry]:
    """Scan all memory files (except MEMORY.md) and return their entries."""
    mem_dir = get_memory_dir(space_id)
    if not os.path.isdir(mem_dir):
        return []

    memories = []
    for fname in sorted(os.listdir(mem_dir)):
        if fname == ENTRYPOINT_NAME or not fname.endswith(".md"):
            continue
        entry = read_memory(space_id, fname)
        if entry:
            memories.append(entry)

    memories.sort(key=lambda m: m.updated or "", reverse=True)
    return memories[:50]


def _sanitize_filename(name: str) -> str:
    """Convert a name to a safe filename."""
    import unicodedata
    sanitized = unicodedata.normalize("NFKD", name)
    sanitized = re.sub(r'[^\w\s-]', '', sanitized)
    sanitized = re.sub(r'[-\s]+', '_', sanitized)
    return sanitized[:80].strip('_') or "untitled"
