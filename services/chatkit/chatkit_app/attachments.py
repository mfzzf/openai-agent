from __future__ import annotations

from chatkit.store import AttachmentStore
from chatkit.types import Attachment, AttachmentCreateParams, FileAttachment, ImageAttachment

from .store import RequestContext, WorkspaceStore


class LocalAttachmentStore(AttachmentStore[RequestContext]):
    def __init__(self, store: WorkspaceStore) -> None:
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
        await self.store.delete_attachment(attachment_id, context)
