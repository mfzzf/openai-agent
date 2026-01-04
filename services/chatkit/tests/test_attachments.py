from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from chatkit_app.attachments import LocalAttachmentStore
from chatkit_app.store import InMemoryStore, RequestContext


@pytest.fixture
def context() -> RequestContext:
    return RequestContext(request_id="test-req", base_url="http://localhost")


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.fixture
def attachment_store(store: InMemoryStore) -> LocalAttachmentStore:
    return LocalAttachmentStore(store)


@pytest.mark.asyncio
async def test_delete_attachment_removes_file_and_record(
    store: InMemoryStore,
    attachment_store: LocalAttachmentStore,
    context: RequestContext,
    tmp_path: Path,
) -> None:
    from chatkit.types import FileAttachment

    attachment = FileAttachment(
        id="att-123",
        name="test.txt",
        mime_type="text/plain",
    )
    await store.save_attachment(attachment, context)

    file_path = tmp_path / "att-123.txt"
    file_path.write_text("test content")
    store.set_attachment_file("att-123", file_path)

    assert store.get_attachment_file("att-123") == file_path
    assert file_path.exists()

    await attachment_store.delete_attachment("att-123", context)

    assert not file_path.exists()
    assert store.get_attachment_file("att-123") is None
    with pytest.raises(Exception):
        await store.load_attachment("att-123", context)


@pytest.mark.asyncio
async def test_delete_attachment_handles_missing_file(
    store: InMemoryStore,
    attachment_store: LocalAttachmentStore,
    context: RequestContext,
) -> None:
    from chatkit.types import FileAttachment

    attachment = FileAttachment(
        id="att-456",
        name="missing.txt",
        mime_type="text/plain",
    )
    await store.save_attachment(attachment, context)

    await attachment_store.delete_attachment("att-456", context)

    with pytest.raises(Exception):
        await store.load_attachment("att-456", context)
