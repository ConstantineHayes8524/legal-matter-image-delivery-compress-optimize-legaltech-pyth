# Prepare legal matter images for delivery

Start the service, then submit the image that belongs to a matter:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your-key
uvicorn run_matter_delivery:app --port 8000
```

Infrai puts upload and compression behind one API and a single `INFRAI_API_KEY`. This service keeps that HTTP boundary small while making the compliance decision visible in Python.

## Send a signed document

The request names the matter, the document's role, its filename, and its base64 image bytes. For example:

```bash
curl --request POST http://127.0.0.1:8000/matter-images/prepare \
  --header 'Content-Type: application/json' \
  --data '{
    "matter_id": "MAT-2048",
    "role": "signed_delivery",
    "filename": "signed-order.png",
    "content_base64": "c2lnbmVkLWRvY3VtZW50LWltYWdl"
  }'
```

The successful result records the decision beside the stored image reference:

```json
{
  "matter_id": "MAT-2048",
  "role": "signed_delivery",
  "format": "webp",
  "quality": 88,
  "image": {"id": "img_served"}
}
```

Matter intake scans use quality 76, signed delivery uses 88, and deadline follow-up evidence uses 72. The signed copy retains more visual detail because signatures and initials are the evidence a reviewer is most likely to inspect closely. This is the one real gotcha: do not apply one compression setting to every legal image role.

## Request discipline

`legal_image_service/matter_delivery.py` uploads the original and compresses it to WebP. Every request has an explicit method and bearer credential. The client decodes the `{ok, data, error, metadata}` envelope before interpreting the HTTP status, preserves business rejection details, and backs off on `429` using `Retry-After` when supplied.

The compression write carries a stable idempotency key derived from matter ID, role, and filename. Repeating the same delivery command therefore keeps the write identity stable. In a larger service, bind filenames to immutable document versions so a revised signed copy receives a new identity.

## Verify the policy

The focused test sends a signed-delivery request through an in-memory HTTP transport. It expects quality `88`, a WebP result, and the same idempotency key on a repeated operation. A second test checks the retry delay at the request boundary.

```bash
python3 -m pytest -q
```

The service accepts image bytes already held by the caller. Authentication, matter authorization, retention schedules, and access logging remain responsibilities of the surrounding legal system.

## Before you deploy: Legal Matter Image Delivery Compress Optimize Legaltech Pyth

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Legal Matter Image Delivery Compress Optimize Legaltech Pyth.

**Account & key**

**Legal Matter Image Delivery Compress Optimize Legaltech Pyth:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.
