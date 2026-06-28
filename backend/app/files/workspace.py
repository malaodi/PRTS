"""
Workspace manager - session file system isolation and path resolution.
Creates per-session directories and resolves files/ prefix for shared files.
"""
import os
import shutil
from uuid import UUID
from typing import Optional

BASE_DATA_DIR = "/data/files"
SESSION_BASE = os.path.join(BASE_DATA_DIR, "sessions")


class SessionWorkspace:
    """Manages file system isolation for a single agent session."""

    def __init__(self, space_id: UUID | str, session_id: str):
        self.space_id = str(space_id)
        self.session_id = session_id
        self.session_dir = os.path.join(SESSION_BASE, self.space_id, session_id)
        self.shared_dir = os.path.join(BASE_DATA_DIR, self.space_id, "shared")
        self.skills_dir = os.path.join(BASE_DATA_DIR, self.space_id, "skills")
        self.tools_dir = os.path.join(BASE_DATA_DIR, self.space_id, "tools")
        self.mcp_dir = os.path.join(BASE_DATA_DIR, self.space_id, "mcp")

    def setup(self):
        """Create all directories for this session."""
        os.makedirs(self.session_dir, exist_ok=True)
        os.makedirs(self.shared_dir, exist_ok=True)
        os.makedirs(self.skills_dir, exist_ok=True)
        os.makedirs(self.tools_dir, exist_ok=True)
        os.makedirs(self.mcp_dir, exist_ok=True)

    def cleanup(self):
        """Remove session directory after agent completes."""
        if os.path.exists(self.session_dir):
            try:
                shutil.rmtree(self.session_dir)
            except Exception:
                pass

    def resolve_path(self, path: str) -> str:
        """
        Resolve a tool-provided path to its actual filesystem location.

        Path rules:
        - `files/xxx` or `./files/xxx` → shared_dir/xxx
        - `xxx` or `./xxx` → session_dir/xxx
        - absolute paths → rejected (security)
        """
        path = path.strip()

        # Reject absolute paths outside allowed directories
        if os.path.isabs(path):
            normalized = os.path.normpath(path)
            allowed = [
                os.path.normpath(self.session_dir),
                os.path.normpath(self.shared_dir),
                os.path.normpath(self.skills_dir),
                os.path.normpath(self.tools_dir),
            ]
            if not any(normalized.startswith(a) for a in allowed):
                return os.path.join(self.session_dir, os.path.basename(path))

        # Remove leading ./ or .\\
        clean = path
        if clean.startswith("./") or clean.startswith(".\\"):
            clean = clean[2:]

        # files/ prefix → shared directory
        if clean.startswith("files/") or clean.startswith("files\\"):
            return os.path.join(self.shared_dir, clean[6:])

        # skills/ prefix → skills directory (read-only)
        if clean.startswith("skills/") or clean.startswith("skills\\"):
            return os.path.join(self.skills_dir, clean[7:])

        # Default → session directory
        return os.path.join(self.session_dir, clean)

    def get_context(self) -> dict:
        """Get workspace context for AgentState.file_context."""
        return {
            "session_dir": self.session_dir,
            "shared_dir": self.shared_dir,
            "skills_dir": self.skills_dir,
            "tools_dir": self.tools_dir,
        }

    def get_env_vars(self) -> dict:
        """Get environment variables for tool execution."""
        return {
            "SESSION_DIR": self.session_dir,
            "SHARED_DIR": self.shared_dir,
            "SKILLS_DIR": self.skills_dir,
            "WORKSPACE": BASE_DATA_DIR,
        }


_workspaces: dict[str, SessionWorkspace] = {}


def get_workspace(space_id: UUID | str, session_id: str) -> SessionWorkspace:
    """Get or create a session workspace. Caches per session_id."""
    key = f"{space_id}_{session_id}"
    if key not in _workspaces:
        ws = SessionWorkspace(space_id, session_id)
        ws.setup()
        _workspaces[key] = ws
    return _workspaces[key]


def clear_workspace(space_id: UUID | str, session_id: str):
    """Remove a workspace from cache and cleanup files."""
    key = f"{space_id}_{session_id}"
    ws = _workspaces.pop(key, None)
    if ws:
        ws.cleanup()
