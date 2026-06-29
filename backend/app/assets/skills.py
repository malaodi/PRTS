"""
Skill system - loads SKILL.md files with YAML frontmatter,
provides trigger keyword matching, and progressive loading of references.
"""
import os
import re
import yaml
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class SkillManifest:
    name: str
    description: str
    trigger_keywords: List[str] = field(default_factory=list)
    body: str = ""
    references_dir: str = ""
    skill_dir: str = ""


def parse_skill_md(file_path: str) -> Optional[SkillManifest]:
    """Parse a SKILL.md file with YAML frontmatter."""
    if not os.path.isfile(file_path):
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        frontmatter, body = _split_frontmatter(content)
        if frontmatter is None:
            return None

        skill_dir = os.path.dirname(file_path)
        refs_dir = os.path.join(skill_dir, "references")

        return SkillManifest(
            name=frontmatter.get("name", os.path.basename(skill_dir)),
            description=frontmatter.get("description", ""),
            trigger_keywords=frontmatter.get("trigger_keywords", []),
            body=body.strip(),
            references_dir=refs_dir if os.path.isdir(refs_dir) else "",
            skill_dir=skill_dir,
        )
    except Exception:
        return None


def _split_frontmatter(content: str) -> Tuple[Optional[dict], str]:
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


def match_skills(user_message: str, skills: List[SkillManifest]) -> List[SkillManifest]:
    """Find skills whose trigger keywords match the user message."""
    if not skills:
        return []

    message_lower = user_message.lower()
    matched = []

    for skill in skills:
        if not skill.trigger_keywords:
            continue
        for keyword in skill.trigger_keywords:
            if keyword.lower() in message_lower:
                matched.append(skill)
                break

    return matched


def load_skill_context(skill: SkillManifest, include_refs: bool = False) -> str:
    """Generate context string for a skill to inject into the system prompt."""
    parts = [f"## 技能: {skill.name}\n{skill.description}\n\n{skill.body}"]

    if include_refs and skill.references_dir and os.path.isdir(skill.references_dir):
        parts.append("\n### 参考资料\n")
        for ref_file in sorted(os.listdir(skill.references_dir)):
            if ref_file.endswith(".md"):
                ref_path = os.path.join(skill.references_dir, ref_file)
                try:
                    with open(ref_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    parts.append(f"\n#### {ref_file}\n{content[:3000]}")
                except Exception:
                    pass

    return "\n".join(parts)


def discover_skills(space_id: str = "") -> List[SkillManifest]:
    """Discover all skills for a space by scanning skill directories.
    Also includes built-in system skills."""
    skills = []

    # User skills from filesystem
    base = "/data/files"
    skills_dir = os.path.join(base, space_id, "skills") if space_id else os.path.join(base, "skills")
    _scan_skills_dir(skills_dir, skills)

    # Built-in system skills
    builtin_skills_dir = os.path.join(os.path.dirname(__file__), "..", "skills")
    builtin_skills_dir = os.path.normpath(builtin_skills_dir)
    _scan_skills_dir(builtin_skills_dir, skills)

    return skills


def _scan_skills_dir(skills_dir: str, skills: list):
    if not os.path.isdir(skills_dir):
        return
    for entry in sorted(os.listdir(skills_dir)):
        skill_path = os.path.join(skills_dir, entry)
        if os.path.isdir(skill_path):
            skill_md = os.path.join(skill_path, "SKILL.md")
            manifest = parse_skill_md(skill_md)
            if manifest:
                skills.append(manifest)


def get_skill_trigger_text(skills: List[SkillManifest]) -> str:
    """Generate the skills section for the system prompt."""
    if not skills:
        return ""

    lines = ["## 可用技能\n"]
    for skill in skills:
        keywords = ", ".join(skill.trigger_keywords) if skill.trigger_keywords else "无特定触发词"
        prefix = " (触发词: " + keywords + ")" if skill.trigger_keywords else ""
        lines.append(f"- **{skill.name}**: {skill.description}{prefix}")

    lines.append(
        "\n> 当用户消息中包含技能触发词时，使用 `read` 工具读取该技能的 SKILL.md 文件获取详细指导。"
    )
    return "\n".join(lines)
