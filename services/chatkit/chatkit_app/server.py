from __future__ import annotations

import base64
import json
from collections.abc import Sequence
from typing import Any, AsyncIterator

from agents import Agent, RunConfig, Runner, StopAtTools
from agents.model_settings import ModelSettings
from chatkit.agents import (
    AgentContext,
    ThreadItemConverter,
    stream_agent_response,
)
from chatkit.server import (
    ChatKitServer,
    NonStreamingResult,
    StreamingResult,
    stream_widget,
)
from chatkit.store import AttachmentStore
from chatkit.types import (
    ChatKitReq,
    ClientToolCallItem,
    ThreadsAddClientToolOutputReq,
    ThreadMetadata,
    ThreadStreamEvent,
    UserMessageItem,
    UserMessageTagContent,
    WidgetRootUpdated,
    ThreadItemUpdatedEvent,
)
from chatkit.widgets import WidgetRoot
from openai.types.responses import (
    ResponseFunctionToolCallParam,
    ResponseInputContentParam,
    ResponseInputFileParam,
    ResponseInputImageParam,
    ResponseInputTextParam,
)
from openai.types.responses.response_input_item_param import FunctionCallOutput, Message
from pydantic import TypeAdapter

from .config import _tool_output_mode
from .store import RequestContext, WorkspaceStore
from .tools import DOTTED_TO_SAFE, TOOL_NAMES, TOOLS
from .widgets import _build_tool_widget, _format_tool_result_message, _sanitize_tool_payload


class CustomThreadItemConverter(ThreadItemConverter):
    def __init__(self, store: WorkspaceStore) -> None:
        self.store = store
        self._latest_desktop_screenshot_call_id: str | None = None

    async def to_agent_input(self, thread_items: Sequence[Any] | Any) -> list[Any]:
        items: list[Any]
        if isinstance(thread_items, Sequence):
            items = list(thread_items)
        else:
            items = [thread_items]

        latest_call_id: str | None = None
        for entry in reversed(items):
            if (
                isinstance(entry, ClientToolCallItem)
                and entry.status != "pending"
                and entry.name == "sandbox.desktop.screenshot"
            ):
                latest_call_id = entry.call_id
                break

        self._latest_desktop_screenshot_call_id = latest_call_id
        try:
            return await super().to_agent_input(items)
        finally:
            self._latest_desktop_screenshot_call_id = None

    def _redact_tool_output_for_model(self, output: Any) -> Any:
        if isinstance(output, dict):
            redacted: dict[str, Any] = {}
            for key, value in output.items():
                if key == "imageBase64" and isinstance(value, str):
                    redacted[key] = f"[base64 omitted: {len(value)} chars]"
                    redacted["imageBytes"] = int(len(value) * 3 / 4)
                    continue
                redacted[key] = self._redact_tool_output_for_model(value)
            return redacted
        if isinstance(output, list):
            return [self._redact_tool_output_for_model(entry) for entry in output]
        return output

    def _desktop_screenshot_to_input(self, item: ClientToolCallItem) -> Message | None:
        if item.name != "sandbox.desktop.screenshot":
            return None
        if (
            self._latest_desktop_screenshot_call_id
            and item.call_id != self._latest_desktop_screenshot_call_id
        ):
            return None
        if not isinstance(item.output, dict):
            return None
        image_base64 = item.output.get("imageBase64")
        if not isinstance(image_base64, str) or not image_base64.strip():
            return None

        mime = item.output.get("mime")
        mime_value = mime if isinstance(mime, str) and mime.strip() else "image/png"

        screen_size = item.output.get("screenSize")
        cursor_position = item.output.get("cursorPosition")
        metadata: dict[str, Any] = {
            "tool": item.name,
            "note": "Coordinates are pixels; origin is top-left of the screenshot.",
        }
        if isinstance(screen_size, dict):
            metadata["screenSize"] = screen_size
        if isinstance(cursor_position, dict):
            metadata["cursorPosition"] = cursor_position

        return Message(
            role="user",
            type="message",
            content=[
                ResponseInputTextParam(
                    type="input_text",
                    text="Desktop screenshot (observation):\n"
                    + json.dumps(metadata, ensure_ascii=True, default=str),
                ),
                ResponseInputImageParam(
                    type="input_image",
                    detail="auto",
                    image_url=f"data:{mime_value};base64,{image_base64}",
                ),
            ],
        )

    async def attachment_to_message_content(
        self, attachment
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
            inputs: list[Any] = [
                ResponseFunctionToolCallParam(
                    type="function_call",
                    call_id=item.call_id,
                    name=item.name,
                    arguments=json.dumps(item.arguments, ensure_ascii=True),
                ),
                FunctionCallOutput(
                    type="function_call_output",
                    call_id=item.call_id,
                    output=json.dumps(
                        self._redact_tool_output_for_model(item.output),
                        ensure_ascii=True,
                        default=str,
                    ),
                ),
            ]
            screenshot_input = self._desktop_screenshot_to_input(item)
            if screenshot_input:
                inputs.append(screenshot_input)
            return inputs

        payload = {
            "name": item.name,
            "arguments": item.arguments,
            "output": self._redact_tool_output_for_model(item.output),
            "call_id": item.call_id,
        }
        text = (
            "Tool execution result (tool already completed):\n"
            + json.dumps(payload, ensure_ascii=True, default=str)
        )
        inputs: list[Any] = [
            Message(
                role="user",
                type="message",
                content=[ResponseInputTextParam(type="input_text", text=text)],
            )
        ]
        screenshot_input = self._desktop_screenshot_to_input(item)
        if screenshot_input:
            inputs.append(screenshot_input)
        return inputs


class WorkspaceChatKitServer(ChatKitServer[RequestContext]):
    def __init__(
        self,
        store: WorkspaceStore,
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
        widget_payload = _sanitize_tool_payload(payload)

        async def _emit_tool_message_and_respond() -> AsyncIterator[ThreadStreamEvent]:
            item_id = self.store.generate_item_id("message", thread, context)
            self._tool_payloads[item_id] = widget_payload
            widget = _build_tool_widget(widget_payload, expanded=False)

            async def _single_widget() -> AsyncIterator[WidgetRoot]:
                yield widget

            async for event in stream_widget(
                thread,
                _single_widget(),
                copy_text=_format_tool_result_message(widget_payload),
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
        if action.type in {"tool.toggle", "agent.tool.toggle"}:
            if sender is None:
                return
            expanded = False
            payload = action.payload or {}
            tool_payload = None
            if isinstance(payload, dict):
                if payload.get("expanded") is not None:
                    expanded = bool(payload.get("expanded"))
                action_tool_payload = payload.get("toolPayload")
                if isinstance(action_tool_payload, dict):
                    tool_payload = action_tool_payload

            if not tool_payload:
                tool_payload = self._tool_payloads.get(sender.id)
            if not tool_payload:
                return

            self._tool_payloads[sender.id] = tool_payload
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

        widget_payload = _sanitize_tool_payload(payload)
        item_id = self.store.generate_item_id("message", thread, context)
        self._tool_payloads[item_id] = widget_payload
        widget = _build_tool_widget(widget_payload, expanded=False)

        async def _single_widget() -> AsyncIterator[WidgetRoot]:
            yield widget

        async for event in stream_widget(
            thread,
            _single_widget(),
            copy_text=_format_tool_result_message(widget_payload),
            generate_id=lambda _item_type: item_id,
        ):
            yield event
