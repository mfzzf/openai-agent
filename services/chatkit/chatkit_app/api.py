from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from chatkit.server import NonStreamingResult, StreamingResult
from chatkit.store import NotFoundError
from chatkit.types import FileAttachment, ImageAttachment
from pydantic import AnyUrl, TypeAdapter

from .attachments import LocalAttachmentStore
from .config import (
    DEFAULT_INSTRUCTIONS,
    DEFAULT_MODEL,
    _env,
    _sqlite_path,
    _store_mode,
    _tool_output_mode,
    loaded_env_path,
)
from .server import WorkspaceChatKitServer
from .store import InMemoryStore, RequestContext, SQLiteStore
from .tracing import configure_tracing

import aiofiles

configure_tracing()

_ANY_URL_ADAPTER = TypeAdapter(AnyUrl)

MAX_UPLOAD_SIZE = int(_env("CHATKIT_MAX_UPLOAD_SIZE") or str(50 * 1024 * 1024))  # 50MB default
UPLOAD_DIR = Path(
    _env("CHATKIT_UPLOAD_DIR") or str(Path(__file__).resolve().parent.parent / "uploads")
).expanduser()


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


def _build_request_context(request: Request) -> RequestContext:
    return RequestContext(
        request_id=uuid.uuid4().hex,
        base_url=_public_base_url(request),
    )


store_mode = _store_mode()
if store_mode == "memory":
    store = InMemoryStore()
else:
    store = SQLiteStore(_sqlite_path())
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
        "chatkit_store": store_mode,
        "chatkit_sqlite_path": str(_sqlite_path()) if store_mode == "sqlite" else None,
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
        "env_loaded_from": str(loaded_env_path()) if loaded_env_path() else None,
    }


@app.post("/files")
async def upload_file(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    context = _build_request_context(request)
    mime_type = file.content_type or "application/octet-stream"
    attachment_id = attachment_store.generate_attachment_id(mime_type, context)
    suffix = Path(file.filename).suffix
    path = UPLOAD_DIR / f"{attachment_id}{suffix}"

    total_size = 0
    async with aiofiles.open(path, "wb") as f:
        while chunk := await file.read(64 * 1024):
            total_size += len(chunk)
            if total_size > MAX_UPLOAD_SIZE:
                await f.close()
                path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"Upload exceeds {MAX_UPLOAD_SIZE} bytes limit")
            await f.write(chunk)

    if total_size == 0:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Empty upload")

    preview_url = _ANY_URL_ADAPTER.validate_python(
        f"{context.base_url}/files/{attachment_id}"
    )
    if mime_type.startswith("image/"):
        attachment = ImageAttachment(
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

    suffix = Path(attachment.name).suffix
    path = UPLOAD_DIR / f"{attachment_id}{suffix}"

    total_size = 0
    async with aiofiles.open(path, "wb") as f:
        async for chunk in request.stream():
            total_size += len(chunk)
            if total_size > MAX_UPLOAD_SIZE:
                await f.close()
                path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"Upload exceeds {MAX_UPLOAD_SIZE} bytes limit")
            await f.write(chunk)

    if total_size == 0:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Empty upload")

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
