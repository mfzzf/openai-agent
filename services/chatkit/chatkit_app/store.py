from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, TypeVar

from chatkit.store import NotFoundError, Store
from chatkit.types import Attachment, Page, ThreadItem, ThreadMetadata
from pydantic import TypeAdapter

T = TypeVar("T")

THREAD_METADATA_ADAPTER = TypeAdapter(ThreadMetadata)
THREAD_ITEM_ADAPTER = TypeAdapter(ThreadItem)
ATTACHMENT_ADAPTER = TypeAdapter(Attachment)


@dataclass
class RequestContext:
    request_id: str
    base_url: str


class WorkspaceStore(Store[RequestContext]):
    def set_attachment_file(self, attachment_id: str, path: Path) -> None:
        raise NotImplementedError

    def get_attachment_file(self, attachment_id: str) -> Optional[Path]:
        raise NotImplementedError


class InMemoryStore(WorkspaceStore):
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


class SQLiteStore(WorkspaceStore):
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._attachment_files: dict[str, Path] = {}
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS threads (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS items (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY(thread_id) REFERENCES threads(id) ON DELETE CASCADE
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS attachments (
                    id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    file_path TEXT
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_items_thread ON items(thread_id, created_at)"
            )
            self._conn.commit()

    def _run_locked(self, fn: Callable[[sqlite3.Connection], T]) -> T:
        with self._lock:
            return fn(self._conn)

    async def _run(self, fn: Callable[[sqlite3.Connection], T]) -> T:
        return await asyncio.to_thread(self._run_locked, fn)

    def _dump_model(self, model: Any) -> str:
        return json.dumps(model.model_dump(mode="json"), ensure_ascii=True, default=str)

    async def load_thread(self, thread_id: str, context: RequestContext) -> ThreadMetadata:
        def _op(conn: sqlite3.Connection) -> Optional[str]:
            row = conn.execute(
                "SELECT payload_json FROM threads WHERE id = ?",
                (thread_id,),
            ).fetchone()
            return row["payload_json"] if row else None

        payload_json = await self._run(_op)
        if payload_json:
            return THREAD_METADATA_ADAPTER.validate_json(payload_json)

        thread = ThreadMetadata(id=thread_id, created_at=datetime.now())
        await self.save_thread(thread, context)
        return thread

    async def save_thread(self, thread: ThreadMetadata, context: RequestContext) -> None:
        payload_json = self._dump_model(thread)
        created_at = thread.created_at.isoformat()

        def _op(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO threads (id, created_at, payload_json)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    created_at = excluded.created_at,
                    payload_json = excluded.payload_json
                """,
                (thread.id, created_at, payload_json),
            )
            conn.commit()

        await self._run(_op)

    async def load_thread_items(
        self,
        thread_id: str,
        after: str | None,
        limit: int,
        order: str,
        context: RequestContext,
    ) -> Page[ThreadItem]:
        order_sql = "DESC" if order == "desc" else "ASC"

        def _op(conn: sqlite3.Connection) -> list[sqlite3.Row]:
            return conn.execute(
                f"""
                SELECT payload_json FROM items
                WHERE thread_id = ?
                ORDER BY created_at {order_sql}, id {order_sql}
                """,
                (thread_id,),
            ).fetchall()

        rows = await self._run(_op)
        items = [THREAD_ITEM_ADAPTER.validate_json(row["payload_json"]) for row in rows]

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
        payload_json = self._dump_model(attachment)

        def _op(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO attachments (id, payload_json, file_path)
                VALUES (?, ?, COALESCE((SELECT file_path FROM attachments WHERE id = ?), NULL))
                ON CONFLICT(id) DO UPDATE SET
                    payload_json = excluded.payload_json
                """,
                (attachment.id, payload_json, attachment.id),
            )
            conn.commit()

        await self._run(_op)

    async def load_attachment(
        self, attachment_id: str, context: RequestContext
    ) -> Attachment:
        def _op(conn: sqlite3.Connection) -> Optional[str]:
            row = conn.execute(
                "SELECT payload_json FROM attachments WHERE id = ?",
                (attachment_id,),
            ).fetchone()
            return row["payload_json"] if row else None

        payload_json = await self._run(_op)
        if not payload_json:
            raise NotFoundError(f"Attachment not found: {attachment_id}")
        return ATTACHMENT_ADAPTER.validate_json(payload_json)

    async def delete_attachment(
        self, attachment_id: str, context: RequestContext
    ) -> None:
        def _op(conn: sqlite3.Connection) -> None:
            conn.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
            conn.commit()

        await self._run(_op)
        self._attachment_files.pop(attachment_id, None)

    async def load_threads(
        self,
        limit: int,
        after: str | None,
        order: str,
        context: RequestContext,
    ) -> Page[ThreadMetadata]:
        order_sql = "DESC" if order == "desc" else "ASC"

        def _op(conn: sqlite3.Connection) -> list[sqlite3.Row]:
            return conn.execute(
                f"""
                SELECT payload_json FROM threads
                ORDER BY created_at {order_sql}, id {order_sql}
                """
            ).fetchall()

        rows = await self._run(_op)
        threads = [
            THREAD_METADATA_ADAPTER.validate_json(row["payload_json"]) for row in rows
        ]

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
        await self.save_item(thread_id, item, context)

    async def save_item(
        self, thread_id: str, item: ThreadItem, context: RequestContext
    ) -> None:
        payload_json = self._dump_model(item)
        created_at = item.created_at.isoformat()
        item_type = getattr(item, "type", "item")

        def _op(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO items (id, thread_id, created_at, type, payload_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    thread_id = excluded.thread_id,
                    created_at = excluded.created_at,
                    type = excluded.type,
                    payload_json = excluded.payload_json
                """,
                (item.id, thread_id, created_at, item_type, payload_json),
            )
            conn.commit()

        await self._run(_op)

    async def load_item(
        self, thread_id: str, item_id: str, context: RequestContext
    ) -> ThreadItem:
        def _op(conn: sqlite3.Connection) -> Optional[str]:
            row = conn.execute(
                "SELECT payload_json FROM items WHERE id = ? AND thread_id = ?",
                (item_id, thread_id),
            ).fetchone()
            return row["payload_json"] if row else None

        payload_json = await self._run(_op)
        if not payload_json:
            raise NotFoundError(f"Item not found: {item_id}")
        return THREAD_ITEM_ADAPTER.validate_json(payload_json)

    async def delete_thread(self, thread_id: str, context: RequestContext) -> None:
        def _op(conn: sqlite3.Connection) -> None:
            conn.execute("DELETE FROM items WHERE thread_id = ?", (thread_id,))
            conn.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
            conn.commit()

        await self._run(_op)

    async def delete_thread_item(
        self, thread_id: str, item_id: str, context: RequestContext
    ) -> None:
        def _op(conn: sqlite3.Connection) -> None:
            conn.execute(
                "DELETE FROM items WHERE id = ? AND thread_id = ?",
                (item_id, thread_id),
            )
            conn.commit()

        await self._run(_op)

    def set_attachment_file(self, attachment_id: str, path: Path) -> None:
        self._attachment_files[attachment_id] = path
        with self._lock:
            self._conn.execute(
                "UPDATE attachments SET file_path = ? WHERE id = ?",
                (str(path), attachment_id),
            )
            self._conn.commit()

    def get_attachment_file(self, attachment_id: str) -> Optional[Path]:
        cached = self._attachment_files.get(attachment_id)
        if cached:
            return cached
        with self._lock:
            row = self._conn.execute(
                "SELECT file_path FROM attachments WHERE id = ?",
                (attachment_id,),
            ).fetchone()
        if not row or not row["file_path"]:
            return None
        path = Path(row["file_path"])
        self._attachment_files[attachment_id] = path
        return path
