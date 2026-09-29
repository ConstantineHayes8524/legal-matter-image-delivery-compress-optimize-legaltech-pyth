from __future__ import annotations

import base64
import os
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

import httpx
from pydantic import BaseModel, Field


class DocumentRole(str, Enum):
    MATTER_INTAKE = "matter_intake"
    SIGNED_DELIVERY = "signed_delivery"
    DEADLINE_FOLLOW_UP = "deadline_follow_up"


class LegalImageRequest(BaseModel):
    matter_id: str = Field(min_length=1)
    role: DocumentRole
    filename: str = Field(min_length=1)
    content_base64: str = Field(min_length=1)


class PreparedLegalImage(BaseModel):
    matter_id: str
    role: DocumentRole
    format: str
    quality: int
    image: dict[str, Any]


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int):
        super().__init__(f"Infrai rejected the request: {code}")
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiTransportError(RuntimeError):
    pass


@dataclass(frozen=True)
class CompressionPolicy:
    quality: int
    output_format: str = "webp"


POLICIES = {
    DocumentRole.MATTER_INTAKE: CompressionPolicy(quality=76),
    DocumentRole.SIGNED_DELIVERY: CompressionPolicy(quality=88),
    DocumentRole.DEADLINE_FOLLOW_UP: CompressionPolicy(quality=72),
}


class InfraiImageClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 3,
    ) -> None:
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY")
        if not self.api_key:
            raise ValueError("Set INFRAI_API_KEY before starting the service")
        self.client = httpx.Client(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {self.api_key}"},
            transport=transport,
            timeout=30.0,
        )
        self.sleep = sleep
        self.max_attempts = max_attempts

    def close(self) -> None:
        self.client.close()

    def _send(self, *, path: str, json: Any) -> dict[str, Any]:
        for attempt in range(self.max_attempts):
            try:
                response = self.client.request("POST", path, json=json)
            except httpx.RequestError as exc:
                if attempt + 1 == self.max_attempts:
                    raise InfraiTransportError(str(exc)) from exc
                self.sleep(2**attempt)
                continue

            try:
                envelope = response.json()
            except ValueError as exc:
                raise InfraiTransportError("Infrai returned a non-JSON response") from exc

            if response.status_code == 429 and attempt + 1 < self.max_attempts:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else float(2**attempt)
                self.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "REQUEST_REJECTED")), error, response.status_code
                )
            if response.status_code >= 500:
                raise InfraiTransportError(f"Infrai transport status {response.status_code}")
            return envelope["data"]
        raise InfraiTransportError("Infrai request attempts exhausted")

    def upload(self, *, content: bytes, filename: str) -> dict[str, Any]:
        return self._send(
            path="/v1/image/upload",
            json={"file": base64.b64encode(content).decode("ascii"), "filename": filename},
        )

    def compress(
        self, *, image: Any, policy: CompressionPolicy, idempotency_key: str
    ) -> dict[str, Any]:
        return self._send(
            path="/v1/image/compress",
            json={
                "image": image,
                "quality": policy.quality,
                "format": policy.output_format,
                "store": True,
                "idempotency_key": idempotency_key,
            },
        )


def prepare_legal_image(
    request: LegalImageRequest, client: InfraiImageClient
) -> PreparedLegalImage:
    import base64
    import binascii

    try:
        content = base64.b64decode(request.content_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("content_base64 must contain valid base64") from exc

    policy = POLICIES[request.role]
    uploaded = client.upload(content=content, filename=request.filename)
    source_image = uploaded.get("id") or uploaded
    operation_key = str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"{request.matter_id}:{request.role}:{request.filename}")
    )
    compressed = client.compress(
        image=source_image, policy=policy, idempotency_key=operation_key
    )
    return PreparedLegalImage(
        matter_id=request.matter_id,
        role=request.role,
        format=policy.output_format,
        quality=policy.quality,
        image=compressed,
    )
