"""Built-in file operation tools for the PRTS agent."""

import os
import re
import glob as glob_mod
from typing import Optional
from langchain_core.tools import tool


@tool
def read(file_path: str, offset: int = 0, limit: int = 2000) -> str:
    """读取文件内容。支持指定 offset(起始行号,从1开始) 和 limit(读取行数)。

    Args:
        file_path: 文件路径
        offset: 起始行号，默认为0（从开头）
        limit: 最大读取行数，默认2000
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        if offset > 0:
            lines = lines[offset - 1:]
        if limit > 0:
            lines = lines[:limit]

        result = ''.join(lines)
        if not result:
            return "(文件为空)"
        return result
    except FileNotFoundError:
        return f"错误: 文件未找到 - {file_path}"
    except PermissionError:
        return f"错误: 没有权限读取 - {file_path}"
    except Exception as e:
        return f"错误: {str(e)}"


@tool
def write(file_path: str, content: str) -> str:
    """将内容写入文件。如果文件已存在，将被覆盖。

    Args:
        file_path: 目标文件路径
        content: 要写入的内容
    """
    try:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"成功写入文件: {file_path} ({len(content)} 字符)"
    except Exception as e:
        return f"错误: {str(e)}"


@tool
def edit(file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """精确替换文件中的字符串。

    Args:
        file_path: 要编辑的文件路径
        old_string: 要被替换的文本（需精确匹配）
        new_string: 替换后的文本
        replace_all: 是否替换所有匹配项，默认只替换第一个
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if old_string not in content:
            return f"错误: 未在文件中找到指定字符串"

        count = content.count(old_string)
        if replace_all:
            new_content = content.replace(old_string, new_string)
            msg = f"替换了所有 {count} 处匹配"
        else:
            new_content = content.replace(old_string, new_string, 1)
            msg = "替换了 1 处匹配"

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return f"成功编辑文件: {file_path} - {msg}"
    except Exception as e:
        return f"错误: {str(e)}"


@tool
def ls(path: str = ".") -> str:
    """列出目录中的文件和子目录。

    Args:
        path: 要列出的目录路径，默认当前目录
    """
    try:
        entries = os.listdir(path)
        if not entries:
            return "(目录为空)"

        result = []
        for name in sorted(entries):
            full = os.path.join(path, name)
            marker = "/" if os.path.isdir(full) else ""
            result.append(f"  {name}{marker}")
        return "\n".join(result)
    except Exception as e:
        return f"错误: {str(e)}"


@tool
def glob_search(pattern: str) -> str:
    """使用 glob 模式搜索匹配的文件。

    Args:
        pattern: glob 模式，如 "**/*.py" 或 "src/*.ts"
    """
    try:
        matches = glob_mod.glob(pattern, recursive=True)
        if not matches:
            return f"未找到匹配 '{pattern}' 的文件"
        return "\n".join(sorted(matches))
    except Exception as e:
        return f"错误: {str(e)}"


@tool
def grep(pattern: str, file_path: str, ignore_case: bool = False, context_lines: int = 0) -> str:
    """在文件中搜索匹配正则表达式的行。

    Args:
        pattern: 正则表达式模式
        file_path: 要搜索的文件路径
        ignore_case: 是否忽略大小写
        context_lines: 显示匹配行上下文的行数
    """
    try:
        flags = re.IGNORECASE if ignore_case else 0
        regex = re.compile(pattern, flags)

        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        results = []
        for i, line in enumerate(lines):
            if regex.search(line):
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                for j in range(start, end):
                    prefix = "> " if j == i else "  "
                    results.append(f"{j + 1}: {prefix}{lines[j].rstrip()}")
                if context_lines > 0 and results:
                    results.append("---")

        if not results:
            return f"未找到匹配 '{pattern}' 的行"
        return "\n".join(results)
    except Exception as e:
        return f"错误: {str(e)}"
