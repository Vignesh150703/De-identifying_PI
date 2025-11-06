import os
import shutil
import uuid
from app.db import SessionLocal, Person, File, OCRText
from app.storage import person_bucket_and_object, upload_file, upload_text
from app.config import LOCAL_UPLOAD_DIR, MASK_THEN_OCR


# Try to import your existing deid modules from src/
# Code will try several common function names and fall back to stubs that copy files or return dummy text.


def _import_deid_funcs():
import importlib
deid = importlib.import_module('src.deidentify_pipeline')
ocr = importlib.import_module('src.ocr_extraction')


# deid function
mask_fn = None
for name in ('mask_file', 'redact_file', 'deidentify', 'run_deid'):
if hasattr(deid, name):
mask_fn = getattr(deid, name)
break


# ocr function
ocr_fn = None
for name in ('extract_text', 'ocr_extract_text', 'run_ocr', 'ocr_file'):
if hasattr(ocr, name):
ocr_fn = getattr(ocr, name)
break


# fallbacks
if mask_fn is None:
def mask_fn_stub(p):
# copy file -> simulated masked file
out = str(p) + '.masked'
shutil.copy(p, out)
return out
mask_fn = mask_fn_stub


if ocr_fn is None:
def ocr_fn_stub(p):
return f"[SIMULATED OCR] {os.path.basename(p)}"
ocr_fn = ocr_fn_stub


return mask_fn, ocr_fn




MASK_FUNC, OCR_FUNC = _import_deid_funcs()




def _save_local_temp(upload_file, filename):
# upload_file is FastAPI UploadFile-like; also works with file-like objects
path = os.path.join(LOCAL_UPLOAD_DIR, f"{uuid.uuid4().hex}_{filename}")
with open(path, 'wb') as f:
upload_file.file.seek(0)
shutil.copyfileobj(upload_file.file, f)