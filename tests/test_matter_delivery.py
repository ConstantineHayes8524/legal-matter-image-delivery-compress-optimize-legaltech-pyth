import base64
import json

import httpx

from legal_image_service.matter_delivery import (
    DocumentRole,
    InfraiImageClient,
    LegalImageRequest,
    prepare_legal_image,
)


def test_signed_delivery_keeps_higher_quality_and_idempotent_boundary() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/v1/image/upload":
            return httpx.Response(200, json={"ok": True, "data": {"id": "img_source"}})
        return httpx.Response(200, json={"ok": True, "data": {"id": "img_served"}})

    client = InfraiImageClient(
        "test-key", transport=httpx.MockTransport(handler), sleep=lambda _: None
    )
    request = LegalImageRequest(
        matter_id="MAT-2048",
        role=DocumentRole.SIGNED_DELIVERY,
        filename="signed-order.png",
        content_base64=base64.b64encode(b"signed-document-image").decode(),
    )

    result = prepare_legal_image(request, client)
    retry = prepare_legal_image(request, client)
    client.close()

    first_payload = json.loads(calls[1].content)
    retry_payload = json.loads(calls[3].content)
    upload_payload = json.loads(calls[0].content)
    assert calls[0].headers["content-type"] == "application/json"
    assert upload_payload == {
        "file": request.content_base64,
        "filename": request.filename,
    }
    assert result.quality == 88
    assert result.role == DocumentRole.SIGNED_DELIVERY
    assert result.image["id"] == "img_served"
    assert first_payload["image"] == "img_source"
    assert first_payload["idempotency_key"] == retry_payload["idempotency_key"]


def test_rate_limit_honors_retry_after() -> None:
    delays: list[float] = []
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "3"},
                json={"ok": False, "error": {}},
            )
        return httpx.Response(200, json={"ok": True, "data": {"id": "img_source"}})

    client = InfraiImageClient(
        "test-key", transport=httpx.MockTransport(handler), sleep=delays.append
    )
    result = client.upload(content=b"scan", filename="intake.png")
    client.close()

    assert result["id"] == "img_source"
    assert delays == [3.0]
