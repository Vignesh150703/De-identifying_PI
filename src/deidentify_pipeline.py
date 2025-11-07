import json
import os
import re
from pathlib import Path

from src.image_redactor import redact_image
from src.ocr_extraction import extract_text_from_pdf, extract_text_from_image
from src.pii_detector import detect_pii


# Note: custom field detection (UHID, REFERRED_BY, REG_NO) is implemented in
# `src/pii_detector.py` and returns RecognizerResult-like objects. We avoid
# duplicating regex-based detection here to prevent overlapping duplicate
# entities causing malformed replacements.


def deidentify(input_path, output_dir="output", redact_image_flag=False):
    os.makedirs(output_dir, exist_ok=True)
    file_ext = os.path.splitext(input_path)[1].lower()
    # Step 1: OCR
    print(f"[INFO] Extracting text from {input_path}")
    if file_ext == ".pdf":
        text = extract_text_from_pdf(input_path)
    else:
        text = extract_text_from_image(input_path)

    # Save raw OCR output so user can inspect original extracted text
    raw_text_path = os.path.join(output_dir, "original_ocr.txt")
    with open(raw_text_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[INFO] Raw OCR text saved at {raw_text_path}")

    # Step 2: Detect PII
    print("[INFO] Detecting PII entities...")
    pii_results = detect_pii(text)

    # Convert presidio RecognizerResult objects (if any) to a uniform list of dicts
    entities = []
    for r in pii_results:
        entities.append({
            "entity_type": r.entity_type.upper(),
            "start": r.start,
            "end": r.end,
            "text": text[r.start : r.end],
        })

    # Deduplicate / resolve overlapping entities coming from analyzer + detector.
    # Sort by start asc, end desc so longer spans come first when starts equal.
    entities_sorted = sorted(entities, key=lambda x: (x["start"], -x["end"]))
    dedup_entities = []
    for ent in entities_sorted:
        if not dedup_entities:
            dedup_entities.append(ent)
            continue
        last = dedup_entities[-1]
        # Exact duplicate span -> skip
        if ent["start"] == last["start"] and ent["end"] == last["end"]:
            continue
        # Overlap: keep the one with the larger span
        if ent["start"] < last["end"]:
            last_span = last["end"] - last["start"]
            ent_span = ent["end"] - ent["start"]
            if ent_span > last_span:
                dedup_entities[-1] = ent
            else:
                # keep last, drop ent
                continue
        else:
            dedup_entities.append(ent)

    entities = dedup_entities

    # Sort entities by start index
    entities.sort(key=lambda x: x["start"]) if entities else None

    # Step 3: Create replacements and metadata
    print("[INFO] Building replacements for anonymization...")
    deid_info = []
    person_count = 0
    # We'll perform replacements in reverse order to keep indices valid
    replacements = []  # list of tuples (start, end, replacement, meta)

    for ent in entities:
        etype = ent["entity_type"]
        orig = ent.get("text", "")
        start = ent["start"]
        end = ent["end"]

        # Do NOT deidentify ages — keep them as-is and record as kept.
        if etype == "AGE":
            deid_info.append({
                "entity_type": etype,
                "original_text": orig,
                "replacement": orig,
                "start": start,
                "end": end,
                "action": "kept",
            })
            # skip adding to replacements so original text remains
            continue

        if etype == "PERSON":
            person_count += 1
            # use bracketed numbered names: [NAME1], [NAME2], ...
            repl = f"[NAME{person_count}]"
        
        elif etype == "EMAIL_ADDRESS":
            repl = "[EMAIL]"
        elif etype == "PHONE_NUMBER":
            repl = "[PHONE]"
        elif etype == "LOCATION":
            repl = "[LOCATION]"
        elif etype in ("REFERRED_BY",):
            repl = "[REFERRED_BY]"
        elif etype in ("REG_NO",):
            repl = "[REG_NO]"
        elif etype in ("UHID",):
            repl = "[UHID]"
        elif etype == "ORG":
            repl = "[ORG]"
        else:
            # default: mask the text length with asterisks
            repl = "*" * max(4, end - start)

        # Preserve leading/trailing whitespace/newlines from the original span
        leading_ws = re.match(r"^\s+", orig)
        trailing_ws = re.search(r"\s+$", orig)
        if leading_ws and not repl.startswith(leading_ws.group(0)):
            repl = leading_ws.group(0) + repl
        if trailing_ws and not repl.endswith(trailing_ws.group(0)):
            repl = repl + trailing_ws.group(0)

        replacements.append((start, end, repl))
        deid_info.append({
            "entity_type": etype,
            "original_text": orig,
            "replacement": repl,
            "start": start,
            "end": end,
        })

    # Build anonymized text by walking the original text and inserting
    # replacements in order. This avoids overlapping-slice issues.
    replacements_sorted = sorted(replacements, key=lambda x: x[0])
    anonymized_parts = []
    cursor = 0
    for start, end, repl in replacements_sorted:
        if start < cursor:
            # overlapping replacement (shouldn't happen after dedupe) -> skip
            continue
        anonymized_parts.append(text[cursor:start])
        anonymized_parts.append(repl)
        cursor = end
    anonymized_parts.append(text[cursor:])
    anonymized = "".join(anonymized_parts)

    # Step 4: Save anonymized text and metadata
    out_text_path = os.path.join(output_dir, "redacted_text.txt")
    with open(out_text_path, "w", encoding="utf-8") as f:
        f.write(anonymized)
    print(f"[SUCCESS] De-identified text saved at {out_text_path}")

    metadata_path = os.path.join(output_dir, "deid_metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump({
            "source": Path(input_path).as_posix(),
            "raw_text_path": Path(raw_text_path).as_posix(),
            "redacted_text_path": Path(out_text_path).as_posix(),
            "entities": deid_info,
        }, f, indent=2)
    print(f"[SUCCESS] De-identification metadata saved at {metadata_path}")

    # Step 5 (optional): Redact image
    if redact_image_flag and file_ext in [".png", ".jpg", ".jpeg"]:
        out_img_path = os.path.join(output_dir, "redacted_image.png")
        redact_image(input_path, out_img_path)
        print(f"[SUCCESS] Redacted image saved at {out_img_path}")

    return anonymized
