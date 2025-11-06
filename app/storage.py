from minio import Minio
from app.config import MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_SECURE, MINIO_BUCKET, USE_PERSON_BUCKET


client = Minio(
MINIO_ENDPOINT,
access_key=MINIO_ACCESS_KEY,
secret_key=MINIO_SECRET_KEY,
secure=MINIO_SECURE
)




def ensure_bucket(bucket_name: str):
if not client.bucket_exists(bucket_name):
client.make_bucket(bucket_name)
return bucket_name




def sanitize_name(name: str) -> str:
import re
if not name:
return "person"
s = name.strip().lower()
s = re.sub(r'[^a-z0-9-_\.]+', '_', s)
return s[:120]




def person_bucket_and_object(person_id: int, filename: str, subfolder: str = "originals", person_name: str | None = None):
if USE_PERSON_BUCKET:
bucket = f"person-{person_id}"
ensure_bucket(bucket)
object_name = f"{subfolder}/{filename}"
return bucket, object_name
else:
bucket = MINIO_BUCKET
ensure_bucket(bucket)
prefix = f"persons/{person_id}"
if person_name:
prefix = f"{prefix}-{sanitize_name(person_name)}"
object_name = f"{prefix}/{subfolder}/{filename}"
return bucket, object_name




def upload_file(bucket: str, object_name: str, file_path: str, content_type: str | None = None) -> dict:
# fput_object returns none; return path & etag query by stat
client.fput_object(bucket, object_name, file_path, content_type=content_type)
stat = client.stat_object(bucket, object_name)
return {"bucket": bucket, "object": object_name, "etag": stat.etag}




def upload_text(bucket: str, object_name: str, text: str):
client.put_object(bucket, object_name, data=bytes(text, "utf-8"), length=len(text))
stat = client.stat_object(bucket, object_name)
return {"bucket": bucket, "object": object_name, "etag": stat.etag}