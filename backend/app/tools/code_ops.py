"""Code execution tools with sandbox support."""

import subprocess
import tempfile
import os
import sys
from pathlib import Path
from langchain_core.tools import tool


DANGEROUS_COMMANDS = [
    "rm -rf /", "mkfs.", "dd if=", ":(){ :|:& };:", "fork bomb",
    "shutdown", "reboot", "halt", "poweroff", "init 0", "init 6",
    "> /dev/sda", "chmod 777 /", "format c:",
]


def _is_dangerous(command: str) -> bool:
    cmd_lower = command.lower()
    for d in DANGEROUS_COMMANDS:
        if d in cmd_lower:
            return True
    return False


@tool
def bash(command: str, timeout: int = 30) -> str:
    """在沙盒环境中执行 Shell/PowerShell 命令。
    危险命令（如 rm -rf /、格式化等）会被系统自动拦截。

    Args:
        command: 要执行的命令
        timeout: 超时时间（秒），默认30秒
    """
    if _is_dangerous(command):
        return f"错误: 命令包含危险操作，已被拦截: {command}"

    try:
        shell = os.environ.get("SHELL", "powershell" if sys.platform == "win32" else "/bin/sh")
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd(),
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n[退出码: {result.returncode}]"
        return output.strip() or "(命令执行成功，无输出)"
    except subprocess.TimeoutExpired:
        return f"错误: 命令执行超时（{timeout}秒）: {command}"
    except Exception as e:
        return f"错误: {str(e)}"


@tool
def execute_python(code: str, timeout: int = 30) -> str:
    """执行 Python 代码并返回结果。代码在隔离的临时环境中运行。

    Args:
        code: 要执行的 Python 代码
        timeout: 超时时间（秒），默认30秒
    """
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.py', delete=False, encoding='utf-8'
        ) as f:
            f.write(code)
            tmp_path = f.name

        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd(),
        )

        os.unlink(tmp_path)

        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n[退出码: {result.returncode}]"
        return output.strip() or "(代码执行成功，无输出)"
    except subprocess.TimeoutExpired:
        return f"错误: 代码执行超时（{timeout}秒）"
    except Exception as e:
        return f"错误: {str(e)}"
