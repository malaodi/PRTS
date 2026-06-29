"""
Widget system - interactive cards rendered by Agent in conversations.
Types: confirm, select, form, display.
"""
import json
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field
from langchain_core.tools import tool


class ConfirmWidget(BaseModel):
    type: Literal["confirm"] = "confirm"
    title: str = Field(description="卡片标题")
    message: str = Field(description="提示消息")
    confirm_label: str = "确认"
    cancel_label: str = "取消"
    danger: bool = False


class SelectOption(BaseModel):
    value: str
    label: str
    description: str = ""


class SelectWidget(BaseModel):
    type: Literal["select"] = "select"
    title: str
    message: str
    options: List[dict]
    multiple: bool = False


class FormField(BaseModel):
    key: str
    label: str
    field_type: str = "text"
    placeholder: str = ""
    required: bool = False
    default: str = ""
    options: List[dict] | None = None  # for select/multiselect/credential types


class FormWidget(BaseModel):
    type: Literal["form"] = "form"
    title: str
    message: str
    fields: List[dict]
    submit_label: str = "提交"


class DisplayWidget(BaseModel):
    type: Literal["display"] = "display"
    title: str
    content: str
    format: str = "markdown"


@tool
def show_widget(
    widget_type: str,
    title: str = "",
    message: str = "",
    options: list | None = None,
    content: str = "",
    confirm_label: str = "确认",
    cancel_label: str = "取消",
    danger: bool = False,
) -> str:
    """展示交互式卡片给用户。用于确认操作、选择方案、填写表单或展示结果。

    Args:
        widget_type: 卡片类型 (confirm/select/form/display)
        title: 卡片标题
        message: 提示消息
        options: 选项列表(仅select类型), 每项含value和label
        content: 展示内容(仅display类型)
        confirm_label: 确认按钮文字
        cancel_label: 取消按钮文字
        danger: 是否为危险操作
    """
    widget = {"type": widget_type, "title": title, "message": message}

    if widget_type == "confirm":
        widget["confirm_label"] = confirm_label
        widget["cancel_label"] = cancel_label
        widget["danger"] = danger
    elif widget_type == "select":
        widget["options"] = options or []
    elif widget_type == "display":
        widget["content"] = content
    elif widget_type == "form":
        widget["fields"] = options or []

    return f"[WIDGET:{json.dumps(widget, ensure_ascii=False)}]"


_WIDGET_REGISTRY: Dict[str, Any] = {}


def register_widget(name: str, template: str):
    _WIDGET_REGISTRY[name] = template


def get_widget(name: str) -> Optional[str]:
    return _WIDGET_REGISTRY.get(name)
