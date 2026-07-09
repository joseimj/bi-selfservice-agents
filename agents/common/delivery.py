"""Entrega de archivos compartida por la subcuadrilla de deliverables.

Sube bytes al bucket de exports y devuelve una URL firmada v4 (expiración
configurable). Los bytes nunca pasan por el texto del modelo.
"""
import datetime
import os
import re

SIGNED_URL_HOURS = int(os.environ.get("EXPORT_URL_EXPIRY_HOURS",
                                      os.environ.get("EXCEL_URL_EXPIRY_HOURS", "24")))

CONTENT_TYPES = {
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pdf": "application/pdf",
}


def timestamped_name(name: str, ext: str) -> str:
    stem = re.sub(r"[^\w\-]+", "_", name).strip("_") or "export"
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{stem}_{stamp}{ext}"


def upload_and_sign(data: bytes, filename: str) -> str:
    import google.auth
    from google.auth.transport import requests as ga_requests
    from google.cloud import storage

    ext = "." + filename.rsplit(".", 1)[-1].lower()
    creds, _ = google.auth.default()
    creds.refresh(ga_requests.Request())
    client = storage.Client(credentials=creds)
    blob = client.bucket(os.environ["EXPORT_BUCKET"]).blob(f"exports/{filename}")
    blob.upload_from_string(data, content_type=CONTENT_TYPES.get(ext, "application/octet-stream"))
    return blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(hours=SIGNED_URL_HOURS),
        service_account_email=getattr(creds, "service_account_email", None),
        access_token=creds.token,
        method="GET",
    )
