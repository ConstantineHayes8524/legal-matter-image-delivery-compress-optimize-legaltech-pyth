from fastapi import FastAPI, HTTPException

from legal_image_service.matter_delivery import (
    InfraiError,
    InfraiImageClient,
    LegalImageRequest,
    PreparedLegalImage,
    prepare_legal_image,
)

app = FastAPI(title="Matter image delivery")


@app.post("/matter-images/prepare", response_model=PreparedLegalImage)
def prepare(request: LegalImageRequest) -> PreparedLegalImage:
    client = InfraiImageClient()
    try:
        return prepare_legal_image(request, client)
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status, detail=exc.detail) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        client.close()

