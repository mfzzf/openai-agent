from __future__ import annotations

import json
from typing import Any

from chatkit.actions import ActionConfig
from chatkit.widgets import Badge, Button, Caption, Card, Markdown, Row, Text


def _extract_tool_payload(payload: dict[str, Any]) -> tuple[str, Any, Any, Any, Any, Any]:
    tool = payload.get("tool") if "tool" in payload else payload.get("name", "tool")
    params = payload.get("params") if "params" in payload else payload.get("arguments", {})
    result = payload.get("result") if "result" in payload else payload.get("output")
    status = payload.get("status")
    call_id = payload.get("callId") if "callId" in payload else payload.get("call_id")
    source = payload.get("source")
    return tool, params, result, status, call_id, source


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
    tool, _params, _result, status, _call_id, _source = _extract_tool_payload(payload)
    toggle_label = "收起" if expanded else "展开"
    toggle_action = ActionConfig(
        type="tool.toggle",
        payload={"expanded": not expanded},
    )

    header_left: list[Any] = [
        Text(
            value=f"调用工具：{tool}",
            size="sm",
            weight="semibold",
            truncate=True,
            maxLines=1,
        )
    ]
    if status:
        badge_color = "success" if status == "success" else "danger"
        header_left.append(
            Badge(label=str(status), color=badge_color, variant="soft", size="sm")
        )

    header = Row(
        children=[
            Row(
                children=header_left,
                gap=4,
                align="center",
                wrap="nowrap",
                flex=1,
                minWidth=0,
            ),
            Button(
                label=toggle_label,
                variant="ghost",
                size="2xs",
                pill=True,
                onClickAction=toggle_action,
            ),
        ],
        align="center",
        justify="between",
        wrap="nowrap",
        width="100%",
    )

    children: list[Any] = [header]
    if expanded:
        meta_parts: list[str] = []
        if status:
            meta_parts.append(f"status: {status}")
        if payload.get("source"):
            meta_parts.append(f"source: {payload.get('source')}")
        if payload.get("callId") or payload.get("call_id"):
            meta_parts.append(
                f"call: {payload.get('callId') or payload.get('call_id')}"
            )
        if meta_parts:
            children.append(Caption(value=" · ".join(meta_parts), color="secondary"))

        detail_sections = _format_tool_detail_sections(payload)
        if detail_sections:
            children.append(Markdown(value="\n".join(detail_sections)))
        else:
            children.append(Markdown(value="（无详情）"))

    return Card(children=children, padding=6, background="surface", size="full")
