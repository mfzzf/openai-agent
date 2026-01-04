from __future__ import annotations

from chatkit_app.tracing import _normalize_otlp_grpc_endpoint, _otlp_grpc_exporter_config


class TestNormalizeOtlpGrpcEndpoint:
    def test_passthrough_authority(self) -> None:
        endpoint, insecure_hint = _normalize_otlp_grpc_endpoint("collector:4317")
        assert endpoint == "collector:4317"
        assert insecure_hint is None

    def test_strips_http_scheme(self) -> None:
        endpoint, insecure_hint = _normalize_otlp_grpc_endpoint("http://localhost:4317")
        assert endpoint == "localhost:4317"
        assert insecure_hint is True

    def test_strips_https_scheme(self) -> None:
        endpoint, insecure_hint = _normalize_otlp_grpc_endpoint("https://collector:4317")
        assert endpoint == "collector:4317"
        assert insecure_hint is False

    def test_strips_path(self) -> None:
        endpoint, insecure_hint = _normalize_otlp_grpc_endpoint("http://localhost:4317/v1/traces")
        assert endpoint == "localhost:4317"
        assert insecure_hint is True

    def test_defaults_port_when_missing(self) -> None:
        endpoint, insecure_hint = _normalize_otlp_grpc_endpoint("http://localhost")
        assert endpoint == "localhost:4317"
        assert insecure_hint is True

    def test_preserves_ipv6_brackets(self) -> None:
        endpoint, insecure_hint = _normalize_otlp_grpc_endpoint("http://[::1]:4317")
        assert endpoint == "[::1]:4317"
        assert insecure_hint is True


class TestOtlpGrpcExporterConfig:
    def test_https_scheme_disables_insecure_default(self) -> None:
        endpoint, insecure = _otlp_grpc_exporter_config("https://localhost:4317", None)
        assert endpoint == "localhost:4317"
        assert insecure is False

    def test_localhost_defaults_insecure(self) -> None:
        endpoint, insecure = _otlp_grpc_exporter_config("localhost:4317", None)
        assert endpoint == "localhost:4317"
        assert insecure is True

    def test_env_overrides_insecure(self) -> None:
        endpoint, insecure = _otlp_grpc_exporter_config("https://collector:4317", "true")
        assert endpoint == "collector:4317"
        assert insecure is True
