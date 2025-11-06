import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
LOCAL_UPLOAD_DIR = Path(os.getenv("LOCAL_UPLOAD_DIR", BASE_DIR / "input"))
LOCAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# MinIO
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() in ("1","true","yes")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "documents")
USE_PERSON_BUCKET = os.getenv("USE_PERSON_BUCKET", "false").lower() in ("1","true","yes")


# Postgres
PG_URI = os.getenv("PG_URI", "postgresql+psycopg2://deiduser:deidpass@postgres:5432/deid_db")


# App behavior
MASK_THEN_OCR = os.getenv("MASK_THEN_OCR", "true").lower() in ("1","true","yes")