from __future__ import annotations

import base64
import json
import os
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, AsyncIterator, Iterable, Optional, Tuple

from agents import Agent, RunConfig, Runner, StopAtTools, function_tool
from agents.model_settings import ModelSettings
from agents.tool_context import ToolContext
from agents.tracing import set_trace_processors, set_tracing_disabled
from agents.tracing.processor_interface import TracingProcessor
from chatkit.agents import (
    AgentContext,
    ClientToolCall,
    ThreadItemConverter,
    stream_agent_response,
)
from chatkit.server import (
    ChatKitServer,
    NonStreamingResult,
    StreamingResult,
    stream_widget,
)
from chatkit.store import AttachmentStore, NotFoundError, Store
from chatkit.types import (
    Attachment,
    AttachmentCreateParams,
    ChatKitReq,
    ClientToolCallItem,
    FileAttachment,
    ImageAttachment,
    Page,
    ThreadsAddClientToolOutputReq,
    ThreadMetadata,
    ThreadItem,
    ThreadItemUpdatedEvent,
    ThreadStreamEvent,
    UserMessageItem,
    UserMessageTagContent,
    WidgetRootUpdated,
)
from chatkit.actions import ActionConfig
from chatkit.widgets import Badge, Button, Caption, Card, Markdown, Row, Text
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import TypeAdapter
from openai.types.responses import (
    ResponseFunctionToolCallParam,
    ResponseInputContentParam,
    ResponseInputFileParam,
    ResponseInputImageParam,
    ResponseInputTextParam,
)
from openai.types.responses.response_input_item_param import FunctionCallOutput, Message

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent.parent
_LOADED_ENV_PATH: Optional[Path] = None


def _parse_env_line(line: str) -> Optional[Tuple[str, str]]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].strip()
    if "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    if not key:
        return None
    return key, value


def _load_env_file(path: Path) -> None:
    try:
        content = path.read_text()
    except OSError:
        return
    for line in content.splitlines():
        parsed = _parse_env_line(line)
        if not parsed:
            continue
        key, value = parsed
        os.environ[key] = value


def _maybe_disable_tracing(base_url: str) -> None:
    if os.getenv("OPENAI_AGENTS_DISABLE_TRACING") is not None:
        return
    trace_mode = (os.getenv("CHATKIT_TRACE_MODE") or "").strip().lower()
    if trace_mode == "otel":
        return
    host = urlparse(base_url).hostname or ""
    if not host.endswith("openai.com"):
        os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "true"


def _bootstrap_env() -> None:
    global _LOADED_ENV_PATH
    env_path = os.getenv("CHATKIT_ENV_FILE")
    candidates = []
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(REPO_ROOT / "apps" / "web" / ".env.local")
    candidates.append(ROOT / ".env.local")
    for path in candidates:
        if path.exists():
            _load_env_file(path)
            _LOADED_ENV_PATH = path
            break

    base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE")
    if base_url:
        os.environ["OPENAI_BASE_URL"] = base_url
        os.environ["OPENAI_API_BASE"] = base_url
        _maybe_disable_tracing(base_url)


_bootstrap_env()

DEFAULT_MODEL = "gpt-5.2"
DEFAULT_INSTRUCTIONS = (
    "You are an agent powering a workspace with a desktop and python panel.\n"
    "Use sandbox_desktop_start to open a desktop when needed, and sandbox_python_run for code.\n"
    "Use ui_open_tab to switch panels, ui_notify for status updates."
)


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped if stripped else default


def _is_truthy(value: Optional[str]) -> bool:
    if not value:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _tool_output_mode() -> str:
    mode = (_env("CHATKIT_TOOL_OUTPUT_MODE", "auto") or "auto").lower()
    if mode not in {"auto", "function", "text"}:
        mode = "auto"
    if mode == "auto":
        base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE") or ""
        if not base_url:
            return "function"
        host = urlparse(base_url).hostname or ""
        return "function" if host.endswith("openai.com") else "text"
    return mode


def _extract_tool_payload(payload: dict[str, Any]) -> tuple[str, Any, Any, Any, Any, Any]:
    tool = payload.get("tool") or payload.get("name") or "tool"
    params = payload.get("params") or payload.get("arguments") or {}
    result = payload.get("result") or payload.get("output")
    status = payload.get("status")
    call_id = payload.get("callId") or payload.get("call_id")
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


def _configure_tracing() -> None:
    mode = (_env("CHATKIT_TRACE_MODE", "openai") or "openai").lower()
    disable_env = _is_truthy(_env("OPENAI_AGENTS_DISABLE_TRACING"))

    if mode == "none":
        set_tracing_disabled(True)
        return

    if mode != "otel":
        set_tracing_disabled(disable_env)
        return

    if disable_env:
        set_tracing_disabled(True)
        return

    try:
        from opentelemetry import trace as otel_trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.trace import Status, StatusCode
    except Exception as exc:
        set_tracing_disabled(True)
        print(f"OTEL tracing disabled: {exc}")
        return

    raw_endpoint = _env("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317") or "localhost:4317"
    endpoint = raw_endpoint
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        endpoint = endpoint.split("://", 1)[1]

    insecure = _is_truthy(_env("OTEL_EXPORTER_OTLP_INSECURE"))
    if not _env("OTEL_EXPORTER_OTLP_INSECURE"):
        if endpoint.startswith(("localhost", "127.0.0.1", "0.0.0.0")):
            insecure = True

    service_name = _env("OTEL_SERVICE_NAME", "openai-agent-chatkit") or "openai-agent-chatkit"
    include_data = _is_truthy(_env("CHATKIT_TRACE_INCLUDE_DATA"))

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=insecure)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    otel_trace.set_tracer_provider(provider)
    tracer = otel_trace.get_tracer("chatkit")

    class OtelTracingProcessor(TracingProcessor):
        def __init__(self) -> None:
            self._traces: dict[str, Any] = {}
            self._spans: dict[str, Any] = {}
            self._lock = threading.Lock()

        def on_trace_start(self, trace) -> None:
            attributes = {
                "openai.trace_id": trace.trace_id,
            }
            if trace.group_id:
                attributes["openai.group_id"] = trace.group_id
            if trace.metadata and include_data:
                attributes["openai.metadata"] = json.dumps(
                    trace.metadata, ensure_ascii=True
                )

            span = tracer.start_span(trace.name, attributes=attributes)
            with self._lock:
                self._traces[trace.trace_id] = span

        def on_trace_end(self, trace) -> None:
            with self._lock:
                span = self._traces.pop(trace.trace_id, None)
            if span is not None:
                span.end()

        def on_span_start(self, span) -> None:
            parent_span = None
            with self._lock:
                if span.parent_id:
                    parent_span = self._spans.get(span.parent_id)
                if parent_span is None:
                    parent_span = self._traces.get(span.trace_id)

            context = (
                otel_trace.set_span_in_context(parent_span)
                if parent_span is not None
                else None
            )
            name = span.span_data.type
            data_name = getattr(span.span_data, "name", None)
            if data_name:
                name = f"{name}:{data_name}"
            attributes = {
                "openai.trace_id": span.trace_id,
                "openai.span_id": span.span_id,
                "openai.span_type": span.span_data.type,
            }
            if span.parent_id:
                attributes["openai.parent_id"] = span.parent_id

            otel_span = tracer.start_span(
                name,
                context=context,
                attributes=attributes,
            )
            with self._lock:
                self._spans[span.span_id] = otel_span

        def on_span_end(self, span) -> None:
            with self._lock:
                otel_span = self._spans.pop(span.span_id, None)
            if otel_span is None:
                return

            if include_data:
                otel_span.set_attribute(
                    "openai.span.data",
                    json.dumps(span.span_data.export(), ensure_ascii=True),
                )

            if span.error:
                otel_span.set_attribute(
                    "openai.span.error",
                    json.dumps(span.error, ensure_ascii=True),
                )
                message = span.error.get("message") if span.error else "span error"
                otel_span.set_status(Status(StatusCode.ERROR, message))

            otel_span.end()

        def shutdown(self) -> None:
            provider.shutdown()

        def force_flush(self) -> None:
            provider.force_flush()

    set_trace_processors([OtelTracingProcessor()])
    set_tracing_disabled(False)


_configure_tracing()


UPLOAD_DIR = Path(_env("CHATKIT_UPLOAD_DIR", str(ROOT / "uploads"))).expanduser()


def _public_base_url(request: Request) -> str:
    configured = _env("CHATKIT_PUBLIC_BASE_URL")
    if configured:
        return configured.rstrip("/")
    return str(request.base_url).rstrip("/")


def _parse_allowed_origins() -> list[str]:
    configured = _env("CHATKIT_ALLOWED_ORIGINS")
    if not configured:
        return ["http://localhost:3000"]
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


@dataclass
class RequestContext:
    request_id: str
    base_url: str


class InMemoryStore(Store[RequestContext]):
    def __init__(self) -> None:
        self._threads: dict[str, ThreadMetadata] = {}
        self._items: dict[str, list[ThreadItem]] = {}
        self._items_by_id: dict[str, dict[str, ThreadItem]] = {}
        self._attachments: dict[str, Attachment] = {}
        self._attachment_files: dict[str, Path] = {}

    async def load_thread(self, thread_id: str, context: RequestContext) -> ThreadMetadata:
        thread = self._threads.get(thread_id)
        if not thread:
            thread = ThreadMetadata(id=thread_id, created_at=datetime.now())
            await self.save_thread(thread, context)
        return thread

    async def save_thread(self, thread: ThreadMetadata, context: RequestContext) -> None:
        self._threads[thread.id] = thread
        self._items.setdefault(thread.id, [])
        self._items_by_id.setdefault(thread.id, {})

    async def load_thread_items(
        self,
        thread_id: str,
        after: str | None,
        limit: int,
        order: str,
        context: RequestContext,
    ) -> Page[ThreadItem]:
        items = list(self._items.get(thread_id, []))
        if order == "desc":
            items = list(reversed(items))

        start_idx = 0
        if after:
            for idx, item in enumerate(items):
                if item.id == after:
                    start_idx = idx + 1
                    break

        page_items = items[start_idx : start_idx + limit]
        has_more = start_idx + limit < len(items)
        after_id = page_items[-1].id if page_items else None
        return Page(data=page_items, has_more=has_more, after=after_id)

    async def save_attachment(
        self, attachment: Attachment, context: RequestContext
    ) -> None:
        self._attachments[attachment.id] = attachment

    async def load_attachment(
        self, attachment_id: str, context: RequestContext
    ) -> Attachment:
        attachment = self._attachments.get(attachment_id)
        if not attachment:
            raise NotFoundError(f"Attachment not found: {attachment_id}")
        return attachment

    async def delete_attachment(
        self, attachment_id: str, context: RequestContext
    ) -> None:
        self._attachments.pop(attachment_id, None)
        self._attachment_files.pop(attachment_id, None)

    async def load_threads(
        self,
        limit: int,
        after: str | None,
        order: str,
        context: RequestContext,
    ) -> Page[ThreadMetadata]:
        threads: Iterable[ThreadMetadata] = self._threads.values()
        threads = sorted(threads, key=lambda t: t.created_at, reverse=order == "desc")
        threads = list(threads)

        start_idx = 0
        if after:
            for idx, thread in enumerate(threads):
                if thread.id == after:
                    start_idx = idx + 1
                    break

        page_threads = threads[start_idx : start_idx + limit]
        has_more = start_idx + limit < len(threads)
        after_id = page_threads[-1].id if page_threads else None
        return Page(data=page_threads, has_more=has_more, after=after_id)

    async def add_thread_item(
        self, thread_id: str, item: ThreadItem, context: RequestContext
    ) -> None:
        items = self._items.setdefault(thread_id, [])
        if item.id in self._items_by_id.setdefault(thread_id, {}):
            await self.save_item(thread_id, item, context)
            return
        items.append(item)
        self._items_by_id[thread_id][item.id] = item

    async def save_item(
        self, thread_id: str, item: ThreadItem, context: RequestContext
    ) -> None:
        items = self._items.setdefault(thread_id, [])
        for idx, existing in enumerate(items):
            if existing.id == item.id:
                items[idx] = item
                break
        else:
            items.append(item)
        self._items_by_id.setdefault(thread_id, {})[item.id] = item

    async def load_item(
        self, thread_id: str, item_id: str, context: RequestContext
    ) -> ThreadItem:
        item = self._items_by_id.get(thread_id, {}).get(item_id)
        if not item:
            raise NotFoundError(f"Item not found: {item_id}")
        return item

    async def delete_thread(self, thread_id: str, context: RequestContext) -> None:
        self._threads.pop(thread_id, None)
        self._items.pop(thread_id, None)
        self._items_by_id.pop(thread_id, None)

    async def delete_thread_item(
        self, thread_id: str, item_id: str, context: RequestContext
    ) -> None:
        items = self._items.get(thread_id, [])
        self._items[thread_id] = [item for item in items if item.id != item_id]
        self._items_by_id.get(thread_id, {}).pop(item_id, None)

    def set_attachment_file(self, attachment_id: str, path: Path) -> None:
        self._attachment_files[attachment_id] = path

    def get_attachment_file(self, attachment_id: str) -> Optional[Path]:
        return self._attachment_files.get(attachment_id)


class LocalAttachmentStore(AttachmentStore[RequestContext]):
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def create_attachment(
        self, input: AttachmentCreateParams, context: RequestContext
    ) -> Attachment:
        attachment_id = self.generate_attachment_id(input.mime_type, context)
        upload_url = f"{context.base_url}/files/{attachment_id}"
        if input.mime_type.startswith("image/"):
            attachment = ImageAttachment(
                id=attachment_id,
                name=input.name,
                mime_type=input.mime_type,
                preview_url=upload_url,
                upload_url=upload_url,
            )
        else:
            attachment = FileAttachment(
                id=attachment_id,
                name=input.name,
                mime_type=input.mime_type,
                upload_url=upload_url,
            )
        await self.store.save_attachment(attachment, context)
        return attachment

    async def delete_attachment(self, attachment_id: str, context: RequestContext) -> None:
        path = self.store.get_attachment_file(attachment_id)
        if path and path.exists():
            try:
                path.unlink()
            except OSError:
                pass


class CustomThreadItemConverter(ThreadItemConverter):
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def attachment_to_message_content(
        self, attachment: Attachment
    ) -> ResponseInputContentParam:
        path = self.store.get_attachment_file(attachment.id)
        if not path or not path.exists():
            raise ValueError(f"Attachment file missing: {attachment.id}")
        data = path.read_bytes()
        encoded = base64.b64encode(data).decode("ascii")
        if attachment.type == "image":
            return ResponseInputImageParam(
                type="input_image",
                detail="auto",
                image_url=f"data:{attachment.mime_type};base64,{encoded}",
            )
        return ResponseInputFileParam(
            type="input_file",
            filename=attachment.name,
            file_data=encoded,
        )

    async def tag_to_message_content(
        self, tag: UserMessageTagContent
    ) -> ResponseInputContentParam:
        payload = json.dumps(tag.data, ensure_ascii=True)
        return ResponseInputTextParam(
            type="input_text",
            text=f"Tag {tag.text}: {payload}",
        )

    async def client_tool_call_to_input(
        self, item
    ) -> Any:
        if item.status == "pending":
            return None

        mode = _tool_output_mode()
        if mode == "function":
            return [
                ResponseFunctionToolCallParam(
                    type="function_call",
                    call_id=item.call_id,
                    name=item.name,
                    arguments=json.dumps(item.arguments, ensure_ascii=True),
                ),
                FunctionCallOutput(
                    type="function_call_output",
                    call_id=item.call_id,
                    output=json.dumps(item.output, ensure_ascii=True),
                ),
            ]

        payload = {
            "name": item.name,
            "arguments": item.arguments,
            "output": item.output,
            "call_id": item.call_id,
        }
        text = (
            "Tool execution result (tool already completed):\n"
            + json.dumps(payload, ensure_ascii=True, default=str)
        )
        return Message(
            role="user",
            type="message",
            content=[ResponseInputTextParam(type="input_text", text=text)],
        )


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


class WorkspaceChatKitServer(ChatKitServer[RequestContext]):
    def __init__(
        self,
        store: InMemoryStore,
        attachment_store: AttachmentStore[RequestContext],
        model: str,
        instructions: str,
    ) -> None:
        super().__init__(store, attachment_store)
        self._model = model
        self._instructions = instructions
        self._converter = CustomThreadItemConverter(store)
        self._tool_payloads: dict[str, dict[str, Any]] = {}

    def _build_agent(self) -> Agent[AgentContext]:
        return Agent(
            name="WorkspaceAgent",
            instructions=self._instructions,
            model=self._model,
            tools=TOOLS,
            tool_use_behavior=StopAtTools(stop_at_tool_names=TOOL_NAMES),
        )

    async def process(
        self, request: str | bytes | bytearray, context: RequestContext
    ) -> StreamingResult | NonStreamingResult:
        parsed_request = TypeAdapter[ChatKitReq](ChatKitReq).validate_json(request)
        if isinstance(parsed_request, ThreadsAddClientToolOutputReq):
            async def _stream_bytes() -> AsyncIterator[bytes]:
                async for event in self._process_tool_output(parsed_request, context):
                    data = self._serialize(event)
                    yield b"data: " + data + b"\n\n"

            return StreamingResult(_stream_bytes())
        return await super().process(request, context)

    async def _process_tool_output(
        self, request: ThreadsAddClientToolOutputReq, context: RequestContext
    ) -> AsyncIterator[ThreadStreamEvent]:
        thread = await self.store.load_thread(request.params.thread_id, context=context)
        items = await self.store.load_thread_items(
            thread.id, None, 1, "desc", context
        )
        tool_call = next(
            (
                item
                for item in items.data
                if isinstance(item, ClientToolCallItem)
                and item.status == "pending"
            ),
            None,
        )
        if not tool_call:
            raise ValueError(
                f"Last thread item in {thread.id} was not a ClientToolCallItem"
            )

        tool_call.output = request.params.result
        tool_call.status = "completed"
        await self.store.save_item(thread.id, tool_call, context=context)
        await self._cleanup_pending_client_tool_call(thread, context)

        status = "success"
        if isinstance(tool_call.output, dict):
            if tool_call.output.get("ok") is False or tool_call.output.get("error"):
                status = "error"

        payload = {
            "tool": tool_call.name,
            "params": tool_call.arguments,
            "result": tool_call.output,
            "status": status,
            "callId": tool_call.call_id,
            "source": "chatkit",
        }

        async def _emit_tool_message_and_respond() -> AsyncIterator[ThreadStreamEvent]:
            item_id = self.store.generate_item_id("message", thread, context)
            self._tool_payloads[item_id] = payload
            widget = _build_tool_widget(payload, expanded=False)

            async def _single_widget() -> AsyncIterator[Card]:
                yield widget

            async for event in stream_widget(
                thread,
                _single_widget(),
                copy_text=_format_tool_result_message(payload),
                generate_id=lambda _item_type: item_id,
            ):
                yield event
            async for event in self.respond(thread, None, context):
                yield event

        async for event in self._process_events(
            thread,
            context,
            _emit_tool_message_and_respond,
        ):
            yield event

    async def respond(
        self,
        thread: ThreadMetadata,
        input_user_message: UserMessageItem | None,
        context: RequestContext,
    ) -> AsyncIterator[ThreadStreamEvent]:
        items = await self.store.load_thread_items(
            thread.id, None, 200, "asc", context
        )
        agent_input = await self._converter.to_agent_input(items.data)
        agent_context = AgentContext(
            thread=thread,
            store=self.store,
            request_context=context,
        )
        run_config = RunConfig(model=self._model)
        if input_user_message:
            model_override = input_user_message.inference_options.model
            if model_override:
                run_config.model = model_override
            tool_choice = input_user_message.inference_options.tool_choice
            if tool_choice:
                tool_id = tool_choice.id
                safe_tool_id = DOTTED_TO_SAFE.get(tool_id, tool_id)
                run_config.model_settings = ModelSettings(
                    tool_choice=safe_tool_id
                )

        result = Runner.run_streamed(
            self._build_agent(),
            agent_input,
            context=agent_context,
            run_config=run_config,
        )
        async for event in stream_agent_response(agent_context, result):
            yield event

    async def action(
        self,
        thread: ThreadMetadata,
        action,
        sender,
        context: RequestContext,
    ) -> AsyncIterator[ThreadStreamEvent]:
        if action.type == "tool.toggle":
            if sender is None:
                return
            expanded = False
            payload = action.payload or {}
            if isinstance(payload, dict) and payload.get("expanded") is not None:
                expanded = bool(payload.get("expanded"))

            tool_payload = self._tool_payloads.get(sender.id)
            if not tool_payload:
                return

            widget = _build_tool_widget(tool_payload, expanded=expanded)
            yield ThreadItemUpdatedEvent(
                item_id=sender.id,
                update=WidgetRootUpdated(widget=widget),
            )
            return

        if action.type not in {"tool", "tool_result"}:
            return

        payload = action.payload or {}
        if not isinstance(payload, dict):
            payload = {"value": payload}

        item_id = self.store.generate_item_id("message", thread, context)
        self._tool_payloads[item_id] = payload
        widget = _build_tool_widget(payload, expanded=False)

        async def _single_widget() -> AsyncIterator[Card]:
            yield widget

        async for event in stream_widget(
            thread,
            _single_widget(),
            copy_text=_format_tool_result_message(payload),
            generate_id=lambda _item_type: item_id,
        ):
            yield event


store = InMemoryStore()
attachment_store = LocalAttachmentStore(store)
server = WorkspaceChatKitServer(
    store=store,
    attachment_store=attachment_store,
    model=_env("CHATKIT_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL,
    instructions=_env("CHATKIT_INSTRUCTIONS", DEFAULT_INSTRUCTIONS) or DEFAULT_INSTRUCTIONS,
)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _build_request_context(request: Request) -> RequestContext:
    return RequestContext(
        request_id=uuid.uuid4().hex,
        base_url=_public_base_url(request),
    )


@app.post("/chatkit")
async def chatkit_endpoint(request: Request) -> Response:
    context = _build_request_context(request)
    try:
        result = await server.process(await request.body(), context)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if isinstance(result, StreamingResult):
        return StreamingResponse(
            result,
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )
    assert isinstance(result, NonStreamingResult)
    return Response(result.json, media_type="application/json")


@app.get("/health")
async def health() -> dict[str, Any]:
    base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE")
    otel_endpoint = _env("OTEL_EXPORTER_OTLP_ENDPOINT")
    return {
        "status": "ok",
        "chatkit_model": _env("CHATKIT_MODEL", DEFAULT_MODEL),
        "chatkit_instructions_set": bool(_env("CHATKIT_INSTRUCTIONS")),
        "openai_base_url": base_url,
        "openai_api_key_set": bool(os.getenv("OPENAI_API_KEY")),
        "openai_tracing_disabled": os.getenv("OPENAI_AGENTS_DISABLE_TRACING", "false"),
        "chatkit_trace_mode": _env("CHATKIT_TRACE_MODE", "openai"),
        "chatkit_tool_output_mode": _tool_output_mode(),
        "otel_exporter_otlp_endpoint": otel_endpoint,
        "otel_service_name": _env("OTEL_SERVICE_NAME"),
        "public_base_url": _env("CHATKIT_PUBLIC_BASE_URL"),
        "allowed_origins": _parse_allowed_origins(),
        "upload_dir": str(UPLOAD_DIR),
        "env_loaded_from": str(_LOADED_ENV_PATH) if _LOADED_ENV_PATH else None,
    }


@app.post("/files")
async def upload_file(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty upload")

    context = _build_request_context(request)
    mime_type = file.content_type or "application/octet-stream"
    attachment_id = attachment_store.generate_attachment_id(mime_type, context)
    suffix = Path(file.filename).suffix
    path = UPLOAD_DIR / f"{attachment_id}{suffix}"
    path.write_bytes(contents)

    preview_url = f"{context.base_url}/files/{attachment_id}"
    if mime_type.startswith("image/"):
        attachment: Attachment = ImageAttachment(
            id=attachment_id,
            name=file.filename,
            mime_type=mime_type,
            preview_url=preview_url,
        )
    else:
        attachment = FileAttachment(
            id=attachment_id,
            name=file.filename,
            mime_type=mime_type,
        )

    await store.save_attachment(attachment, context)
    store.set_attachment_file(attachment_id, path)
    return attachment.model_dump()


@app.put("/files/{attachment_id}")
async def upload_file_by_id(attachment_id: str, request: Request) -> dict[str, Any]:
    context = _build_request_context(request)
    attachment = await store.load_attachment(attachment_id, context)
    contents = await request.body()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty upload")

    suffix = Path(attachment.name).suffix
    path = UPLOAD_DIR / f"{attachment_id}{suffix}"
    path.write_bytes(contents)
    store.set_attachment_file(attachment_id, path)

    if getattr(attachment, "upload_url", None):
        attachment = attachment.model_copy(update={"upload_url": None})
        await store.save_attachment(attachment, context)

    return {"ok": True}


@app.get("/files/{attachment_id}")
async def get_file(attachment_id: str, request: Request) -> FileResponse:
    context = _build_request_context(request)
    attachment = await store.load_attachment(attachment_id, context)
    path = store.get_attachment_file(attachment_id)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Attachment file missing")
    return FileResponse(
        path,
        media_type=attachment.mime_type,
        filename=attachment.name,
    )
