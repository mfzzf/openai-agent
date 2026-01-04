from __future__ import annotations

import json
from typing import Any

from chatkit.actions import ActionConfig
from chatkit.widgets import (
    Badge,
    Box,
    Button,
    Caption,
    Card,
    Col,
    Divider,
    Icon,
    Markdown,
    Row,
    Spacer,
    Text,
)


def _extract_tool_payload(payload: dict[str, Any]) -> tuple[str, Any, Any, Any, Any, Any]:
    tool = payload.get("tool") if "tool" in payload else payload.get("name", "tool")
    params = payload.get("params") if "params" in payload else payload.get("arguments", {})
    result = payload.get("result") if "result" in payload else payload.get("output")
    status = payload.get("status")
    call_id = payload.get("callId") if "callId" in payload else payload.get("call_id")
    source = payload.get("source")
    return tool, params, result, status, call_id, source


def _sanitize_tool_payload(payload: dict[str, Any]) -> dict[str, Any]:
    # Ensure payload is JSON-serializable for widget actions.
    return json.loads(json.dumps(payload, ensure_ascii=True, default=str))


def _format_tool_title(tool: str, payload: dict[str, Any]) -> str:
    action = payload.get("action")
    if action:
        return f"{tool}.{action}" if tool else str(action)
    return tool


def _format_time_caption(payload: dict[str, Any]) -> str | None:
    time_value = payload.get("time") or payload.get("timestamp") or payload.get("created_at")
    elapsed_value = (
        payload.get("elapsed")
        or payload.get("elapsedMs")
        or payload.get("duration")
        or payload.get("durationMs")
    )

    time_text = ""
    if isinstance(time_value, str) and time_value.strip():
        time_text = time_value.strip()
    elif isinstance(time_value, (int, float)):
        time_text = str(time_value)

    elapsed_text = ""
    if isinstance(elapsed_value, (int, float)):
        elapsed_ms = float(elapsed_value)
        elapsed_text = f"{elapsed_ms:.0f}ms" if elapsed_ms < 10000 else f"{elapsed_ms / 1000:.1f}s"
    elif isinstance(elapsed_value, str) and elapsed_value.strip():
        elapsed_text = elapsed_value.strip()

    if time_text and elapsed_text:
        return f"{time_text} • {elapsed_text}"
    return time_text or elapsed_text or None


def _format_tool_input_markdown(params: Any) -> str | None:
    if isinstance(params, dict):
        code = params.get("code")
        if isinstance(code, str) and code.strip():
            return "\n".join(["```python", code.rstrip(), "```"])
        params_text = json.dumps(params, ensure_ascii=True, default=str)
        if params_text and params_text != "{}":
            return "\n".join(["```json", params_text, "```"])
    elif params:
        return "\n".join(["```", str(params), "```"])
    return None


def _format_tool_output_markdown(result: Any) -> str | None:
    if isinstance(result, dict):
        lines: list[str] = []
        stdout = result.get("stdout")
        stderr = result.get("stderr")
        error = result.get("error")

        stdout_text = ""
        if isinstance(stdout, list):
            stdout_text = "".join(stdout)
        elif isinstance(stdout, str):
            stdout_text = stdout

        stderr_text = ""
        if isinstance(stderr, list):
            stderr_text = "".join(stderr)
        elif isinstance(stderr, str):
            stderr_text = stderr

        if stdout_text.strip():
            lines.extend(["**Stdout**", "```", stdout_text.rstrip(), "```"])

        if stderr_text.strip():
            lines.extend(["**Stderr**", "```", stderr_text.rstrip(), "```"])

        if error:
            lines.extend(
                [
                    "**Error**",
                    "```json",
                    json.dumps(error, ensure_ascii=True, default=str),
                    "```",
                ]
            )

        if lines:
            return "\n".join(lines)
    elif result is not None:
        return "\n".join(["```json", json.dumps(result, ensure_ascii=True, default=str), "```"])
    return None


def _format_tool_detail_sections(payload: dict[str, Any]) -> list[str]:
    _tool, params, result, _status, _call_id, _source = _extract_tool_payload(payload)
    lines: list[str] = []

    if isinstance(params, dict):
        code = params.get("code")
        if isinstance(code, str) and code.strip():
            lines.append("```python")
            lines.append(code.rstrip())
            lines.append("```")
        else:
            params_text = json.dumps(params, ensure_ascii=True, default=str)
            if params_text and params_text != "{}":
                lines.append("参数:")
                lines.append("```json")
                lines.append(params_text)
                lines.append("```")
    elif params:
        lines.append("参数:")
        lines.append("```")
        lines.append(str(params))
        lines.append("```")

    if isinstance(result, dict):
        stdout = result.get("stdout")
        stderr = result.get("stderr")
        error = result.get("error")

        stdout_text = ""
        if isinstance(stdout, list):
            stdout_text = "".join(stdout)
        elif isinstance(stdout, str):
            stdout_text = stdout

        stderr_text = ""
        if isinstance(stderr, list):
            stderr_text = "".join(stderr)
        elif isinstance(stderr, str):
            stderr_text = stderr

        if stdout_text.strip():
            lines.append("Stdout:")
            lines.append("```")
            lines.append(stdout_text.rstrip())
            lines.append("```")

        if stderr_text.strip():
            lines.append("Stderr:")
            lines.append("```")
            lines.append(stderr_text.rstrip())
            lines.append("```")

        if error:
            lines.append("Error:")
            lines.append("```")
            lines.append(json.dumps(error, ensure_ascii=True, default=str))
            lines.append("```")
    elif result is not None:
        lines.append("Result:")
        lines.append("```")
        lines.append(json.dumps(result, ensure_ascii=True, default=str))
        lines.append("```")

    return lines


def _format_tool_result_message(payload: dict[str, Any]) -> str:
    tool, _params, _result, status, call_id, source = _extract_tool_payload(payload)
    lines: list[str] = ["type:tool", f"tool:{tool}"]
    if status:
        lines.append(f"status:{status}")
    if call_id:
        lines.append(f"call_id:{call_id}")
    if source:
        lines.append(f"source:{source}")

    detail_lines = _format_tool_detail_sections(payload)
    if detail_lines:
        lines.append("")
        lines.extend(detail_lines)

    return "\n".join(lines).strip()


def _build_tool_widget(payload: dict[str, Any], expanded: bool) -> Card:
    tool, params, result, status, call_id, _source = _extract_tool_payload(payload)
    tool_title = _format_tool_title(tool, payload)
    status_value = str(status) if status else ("running" if result is None else "unknown")
    if status_value in {"success"}:
        status_badge = "success"
    elif status_value in {"error", "failed"}:
        status_badge = "danger"
    elif status_value in {"running", "pending"}:
        status_badge = "warning"
    else:
        status_badge = "secondary"

    time_caption = _format_time_caption(payload)
    toggle_label = "收起" if expanded else "详情"
    toggle_action = ActionConfig(
        type="agent.tool.toggle",
        payload={
            "id": call_id or tool,
            "expanded": not expanded,
            "toolPayload": _sanitize_tool_payload(payload),
        },
    )

    header_children: list[Any] = [
        Box(
            children=[Icon(name="square-code", size="lg")],
            background="alpha-10",
            radius="sm",
            padding=1.5,
        ),
        Text(
            value=tool_title,
            size="sm",
            weight="semibold",
            maxLines=1,
            truncate=True,
        ),
        Spacer(),
    ]
    if time_caption:
        header_children.append(Caption(value=time_caption))
    header_children.append(Badge(label=status_value, color=status_badge))
    header_children.append(
        Button(
            label=toggle_label,
            variant="outline",
            size="xs",
            onClickAction=toggle_action,
        )
    )

    header = Row(
        children=header_children,
        gap=3,
        align="center",
        wrap="nowrap",
        width="100%",
    )

    children: list[Any] = [header]
    if expanded:
        input_markdown = _format_tool_input_markdown(params)
        output_markdown = _format_tool_output_markdown(result)
        status_key = str(status).lower() if isinstance(status, str) else ""
        output_placeholder = "执行中…" if status_key in {"running", "pending"} else "尚无输出"

        detail_children: list[Any] = [
            Divider(spacing=2),
            Caption(value="输入"),
        ]
        if input_markdown:
            detail_children.append(Markdown(value=input_markdown))
        else:
            detail_children.append(Text(value="（无输入）", size="sm", color="secondary"))

        detail_children.append(Caption(value="输出"))
        if output_markdown:
            detail_children.append(Markdown(value=output_markdown))
        else:
            detail_children.append(Text(value=output_placeholder, size="sm", color="secondary"))

        children.append(Col(children=detail_children, gap=2, width="100%", padding={"top": 2}))

    return Card(children=children, padding=6, background="surface", size="full")
