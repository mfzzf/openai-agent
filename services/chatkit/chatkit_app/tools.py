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


@function_tool(name_override="sandbox_desktop_set_timeout")
def sandbox_desktop_set_timeout(
    ctx: ToolContext[Any],
    timeoutSeconds: int,
    threadId: Optional[str] = None,
) -> dict[str, Any]:
    thread_id = threadId or ctx.context.thread.id
    return _tool_result(
        ctx,
        "sandbox.desktop.setTimeout",
        {"threadId": thread_id, "timeoutSeconds": timeoutSeconds},
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


@function_tool(name_override="sandbox_desktop_click")
def sandbox_desktop_click(
    ctx: ToolContext[Any],
    x: int,
    y: int,
    button: Optional[str] = None,
    double: Optional[bool] = None,
    threadId: Optional[str] = None,
) -> dict[str, Any]:
    thread_id = threadId or ctx.context.thread.id
    return _tool_result(
        ctx,
        "sandbox.desktop.click",
        {
            "threadId": thread_id,
            "x": x,
            "y": y,
            "button": button,
            "double": double,
        },
    )


@function_tool(name_override="sandbox_desktop_type")
def sandbox_desktop_type(
    ctx: ToolContext[Any],
    text: str,
    chunkSize: Optional[int] = None,
    delayInMs: Optional[int] = None,
    threadId: Optional[str] = None,
) -> dict[str, Any]:
    thread_id = threadId or ctx.context.thread.id
    return _tool_result(
        ctx,
        "sandbox.desktop.type",
        {
            "threadId": thread_id,
            "text": text,
            "chunkSize": chunkSize,
            "delayInMs": delayInMs,
        },
    )


@function_tool(name_override="sandbox_desktop_press")
def sandbox_desktop_press(
    ctx: ToolContext[Any],
    keys: list[str],
    threadId: Optional[str] = None,
) -> dict[str, Any]:
    thread_id = threadId or ctx.context.thread.id
    return _tool_result(
        ctx,
        "sandbox.desktop.press",
        {
            "threadId": thread_id,
            "keys": keys,
        },
    )


@function_tool(name_override="sandbox_desktop_wait")
def sandbox_desktop_wait(
    ctx: ToolContext[Any], ms: int, threadId: Optional[str] = None
) -> dict[str, Any]:
    thread_id = threadId or ctx.context.thread.id
    return _tool_result(
        ctx,
        "sandbox.desktop.wait",
        {
            "threadId": thread_id,
            "ms": ms,
        },
    )


@function_tool(name_override="sandbox_desktop_scroll")
def sandbox_desktop_scroll(
    ctx: ToolContext[Any],
    direction: Optional[str] = None,
    amount: Optional[int] = None,
    threadId: Optional[str] = None,
) -> dict[str, Any]:
    thread_id = threadId or ctx.context.thread.id
    return _tool_result(
        ctx,
        "sandbox.desktop.scroll",
        {
            "threadId": thread_id,
            "direction": direction,
            "amount": amount,
        },
    )


@function_tool(name_override="sandbox_desktop_move_mouse")
def sandbox_desktop_move_mouse(
    ctx: ToolContext[Any],
    x: int,
    y: int,
    threadId: Optional[str] = None,
) -> dict[str, Any]:
    thread_id = threadId or ctx.context.thread.id
    return _tool_result(
        ctx,
        "sandbox.desktop.moveMouse",
        {
            "threadId": thread_id,
            "x": x,
            "y": y,
        },
    )


@function_tool(name_override="sandbox_desktop_drag")
def sandbox_desktop_drag(
    ctx: ToolContext[Any],
    fromX: int,
    fromY: int,
    toX: int,
    toY: int,
    threadId: Optional[str] = None,
) -> dict[str, Any]:
    thread_id = threadId or ctx.context.thread.id
    return _tool_result(
        ctx,
        "sandbox.desktop.drag",
        {
            "threadId": thread_id,
            "fromX": fromX,
            "fromY": fromY,
            "toX": toX,
            "toY": toY,
        },
    )


@function_tool(name_override="sandbox_desktop_screenshot")
def sandbox_desktop_screenshot(
    ctx: ToolContext[Any],
    threadId: Optional[str] = None,
    includeCursor: Optional[bool] = None,
    includeScreenSize: Optional[bool] = None,
) -> dict[str, Any]:
    thread_id = threadId or ctx.context.thread.id
    return _tool_result(
        ctx,
        "sandbox.desktop.screenshot",
        {
            "threadId": thread_id,
            "includeCursor": includeCursor,
            "includeScreenSize": includeScreenSize,
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
    "sandbox_desktop_set_timeout": "sandbox.desktop.setTimeout",
    "sandbox_python_run": "sandbox.python.run",
    "sandbox_desktop_click": "sandbox.desktop.click",
    "sandbox_desktop_type": "sandbox.desktop.type",
    "sandbox_desktop_press": "sandbox.desktop.press",
    "sandbox_desktop_wait": "sandbox.desktop.wait",
    "sandbox_desktop_scroll": "sandbox.desktop.scroll",
    "sandbox_desktop_move_mouse": "sandbox.desktop.moveMouse",
    "sandbox_desktop_drag": "sandbox.desktop.drag",
    "sandbox_desktop_screenshot": "sandbox.desktop.screenshot",
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
    sandbox_desktop_set_timeout,
    sandbox_python_run,
    sandbox_desktop_click,
    sandbox_desktop_type,
    sandbox_desktop_press,
    sandbox_desktop_wait,
    sandbox_desktop_scroll,
    sandbox_desktop_move_mouse,
    sandbox_desktop_drag,
    sandbox_desktop_screenshot,
    ui_open_tab,
    ui_notify,
    ui_open_desktop_panel,
    ui_open_python_panel,
]
