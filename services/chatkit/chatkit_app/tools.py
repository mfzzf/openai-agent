from __future__ import annotations

from typing import Any, Optional

from agents import function_tool
from agents.tool_context import ToolContext
from chatkit.agents import ClientToolCall


def _tool_result(
    ctx: ToolContext[Any], name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    ctx.context.client_tool_call = ClientToolCall(name=name, arguments=arguments)
    return {"ok": True}


@function_tool(name_override="sandbox_desktop_start")
def sandbox_desktop_start(
    ctx: ToolContext[Any],
    threadId: Optional[str] = None,
    viewOnly: Optional[bool] = None,
    requireAuth: Optional[bool] = None,
) -> dict[str, Any]:
    thread_id = threadId or ctx.context.thread.id
    return _tool_result(
        ctx,
        "sandbox.desktop.start",
        {
            "threadId": thread_id,
            "viewOnly": viewOnly,
            "requireAuth": requireAuth,
        },
    )


@function_tool(name_override="sandbox_desktop_stop")
def sandbox_desktop_stop(
    ctx: ToolContext[Any], threadId: Optional[str] = None
) -> dict[str, Any]:
    thread_id = threadId or ctx.context.thread.id
    return _tool_result(
        ctx,
        "sandbox.desktop.stop",
        {"threadId": thread_id},
    )


@function_tool(name_override="sandbox_python_run")
def sandbox_python_run(
    ctx: ToolContext[Any],
    code: str,
    threadId: Optional[str] = None,
    timeoutSeconds: Optional[int] = None,
) -> dict[str, Any]:
    thread_id = threadId or ctx.context.thread.id
    return _tool_result(
        ctx,
        "sandbox.python.run",
        {
            "threadId": thread_id,
            "code": code,
            "timeoutSeconds": timeoutSeconds,
        },
    )


@function_tool(name_override="ui_open_tab")
def ui_open_tab(ctx: ToolContext[Any], tab: str) -> dict[str, Any]:
    return _tool_result(ctx, "ui.openTab", {"tab": tab})


@function_tool(name_override="ui_notify")
def ui_notify(ctx: ToolContext[Any], level: str, message: str) -> dict[str, Any]:
    return _tool_result(ctx, "ui.notify", {"level": level, "message": message})


@function_tool(name_override="ui_open_desktop_panel")
def ui_open_desktop_panel(
    ctx: ToolContext[Any], streamUrl: str, viewOnly: Optional[bool] = None
) -> dict[str, Any]:
    return _tool_result(
        ctx,
        "ui.openDesktopPanel",
        {"streamUrl": streamUrl, "viewOnly": viewOnly},
    )


@function_tool(name_override="ui_open_python_panel")
def ui_open_python_panel(ctx: ToolContext[Any]) -> dict[str, Any]:
    return _tool_result(ctx, "ui.openPythonPanel", {})


TOOL_NAME_MAP = {
    "sandbox_desktop_start": "sandbox.desktop.start",
    "sandbox_desktop_stop": "sandbox.desktop.stop",
    "sandbox_python_run": "sandbox.python.run",
    "ui_open_tab": "ui.openTab",
    "ui_notify": "ui.notify",
    "ui_open_desktop_panel": "ui.openDesktopPanel",
    "ui_open_python_panel": "ui.openPythonPanel",
}

DOTTED_TO_SAFE = {value: key for key, value in TOOL_NAME_MAP.items()}

TOOL_NAMES = list(TOOL_NAME_MAP.keys())

TOOLS = [
    sandbox_desktop_start,
    sandbox_desktop_stop,
    sandbox_python_run,
    ui_open_tab,
    ui_notify,
    ui_open_desktop_panel,
    ui_open_python_panel,
]
