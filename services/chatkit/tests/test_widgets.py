from __future__ import annotations

import pytest

from chatkit_app.widgets import _extract_tool_payload, _format_tool_result_message


class TestExtractToolPayload:
    def test_falsey_result_zero(self) -> None:
        payload = {"tool": "calc", "result": 0}
        tool, params, result, status, call_id, source = _extract_tool_payload(payload)
        assert tool == "calc"
        assert result == 0

    def test_falsey_result_false(self) -> None:
        payload = {"tool": "check", "result": False}
        _, _, result, _, _, _ = _extract_tool_payload(payload)
        assert result is False

    def test_falsey_result_empty_string(self) -> None:
        payload = {"tool": "echo", "result": ""}
        _, _, result, _, _, _ = _extract_tool_payload(payload)
        assert result == ""

    def test_falsey_params_empty_dict(self) -> None:
        payload = {"tool": "noop", "params": {}}
        _, params, _, _, _, _ = _extract_tool_payload(payload)
        assert params == {}

    def test_fallback_to_name_and_arguments(self) -> None:
        payload = {"name": "my_tool", "arguments": {"x": 1}, "output": 42}
        tool, params, result, _, _, _ = _extract_tool_payload(payload)
        assert tool == "my_tool"
        assert params == {"x": 1}
        assert result == 42

    def test_tool_takes_precedence_over_name(self) -> None:
        payload = {"tool": "primary", "name": "secondary"}
        tool, _, _, _, _, _ = _extract_tool_payload(payload)
        assert tool == "primary"

    def test_call_id_fallback(self) -> None:
        payload = {"tool": "t", "call_id": "cid-123"}
        _, _, _, _, call_id, _ = _extract_tool_payload(payload)
        assert call_id == "cid-123"

    def test_callId_takes_precedence(self) -> None:
        payload = {"tool": "t", "callId": "primary", "call_id": "secondary"}
        _, _, _, _, call_id, _ = _extract_tool_payload(payload)
        assert call_id == "primary"


class TestFormatToolResultMessage:
    def test_includes_zero_result(self) -> None:
        payload = {"tool": "calc", "result": 0, "status": "success"}
        msg = _format_tool_result_message(payload)
        assert "Result:" in msg
        assert "0" in msg

    def test_includes_false_result(self) -> None:
        payload = {"tool": "check", "result": False, "status": "success"}
        msg = _format_tool_result_message(payload)
        assert "Result:" in msg
        assert "false" in msg
