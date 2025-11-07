import re
from typing import Iterable, List

from presidio_analyzer import (AnalyzerEngine, Pattern, PatternRecognizer,
                               RecognizerRegistry, RecognizerResult)


# --- Analyzer setup ---------------------------------------------------------------------------

_registry = RecognizerRegistry()
_registry.load_predefined_recognizers()

_custom_recognizers: List[PatternRecognizer] = [
    PatternRecognizer(
        supported_entity="REFERRED_BY",
        patterns=[
            Pattern(
                name="referred_by",
                regex=r"Referred By[:\s]*(?:Dr\.?\s+)?[A-Za-z][A-Za-z .,'-]+",
                score=0.9,
            )
        ],
        context=["Referred", "By"],
    ),
    PatternRecognizer(
        supported_entity="REG_NO",
        patterns=[
            Pattern(
                name="registration_number",
                regex=r"Reg(?:\.|istration)?\.?\s*(?:No|Number)[:\.\s]*[A-Za-z0-9-/]+",
                score=0.9,
            )
        ],
        context=["Reg"],
    ),
    PatternRecognizer(
        supported_entity="UHID",
        patterns=[
            Pattern(
                name="uhid",
                regex=r"UHID[:\s]*[A-Za-z0-9-]+",
                score=0.9,
            )
        ],
        context=["UHID"],
    ),
    PatternRecognizer(
        supported_entity="ORG",
        patterns=[
            Pattern(
                name="facility_header",
                regex=r"[A-Z][A-Za-z '&-]+(?:Hospital|Diagnostic Center|Medical Center)",
                score=0.85,
            )
        ],
        context=["Hospital", "Diagnostic", "Center"],
    ),
    PatternRecognizer(
        supported_entity="LOCATION",
        patterns=[
            Pattern(
                name="address_line",
                regex=r"(?:\d{1,4}[\s,-])?[A-Za-z0-9 '&.-]+(?:Road|Street|St\.|Rd\.|Avenue|Colony|Block|Lane|Nagar|Delhi|New Delhi|India|Zip|Pin|City)\b[ A-Za-z0-9,.-]*",
                score=0.85,
            )
        ],
        context=["Road", "Street", "City", "Delhi", "Hospital"],
    ),
    PatternRecognizer(
        supported_entity="PERSON",
        patterns=[
            Pattern(
                name="patient_name",
                regex=r"Patient Name[:\s]*(?:Mr\.?|Mrs\.?|Ms\.?|Dr\.?)?\s*[A-Z][A-Za-z .'-]+(?=\s+Age\b)",
                score=0.85,
            )
        ],
        context=["Patient", "Name"],
    ),
]

for _rec in _custom_recognizers:
    _registry.add_recognizer(_rec)

analyzer = AnalyzerEngine(registry=_registry)


# --- Heuristic controls ----------------------------------------------------------------------

_LAB_DENYLIST = {
    "absent",
    "absen",
    "present",
    "clear",
    "pale",
    "yellow",
    "ml",
    "hpf",
    "r.b.c.",
    "r.b.c",
    "pus",
    "cells",
    "bacteria",
    "others",
    "crystals",
    "ketone",
    "bilirubin",
    "nitrite",
    "colour",
    "transparency",
}

_PERSON_CUES = re.compile(r"(patient\s+name|name:|mr\.|mrs\.|ms\.|dr\.|referred\s+by)", re.IGNORECASE)
_FACILITY_KEYWORDS = ("hospital", "diagnostic", "center", "clinic", "medical")
_CREDENTIAL_WHITELIST = {"md", "mbbs", "dmlt", "dm", "mch", "phd"}
_LOCATION_DENYLIST = {
    "patient",
    "name",
    "test",
    "profile",
    "sul",
    "lube",
    "specimen",
    "microscopic",
    "examination",
    "interpretation",
    "scan",
    "qr",
    "code",
    "information",
    "client",
    "status",
    "sample",
    "process",
    "location",
}
_LOCATION_KEYWORDS = {
    "road",
    "street",
    "st.",
    "rd.",
    "avenue",
    "colony",
    "block",
    "lane",
    "nagar",
    "delhi",
    "gujarat",
    "india",
    "floor",
    "cross",
    "mandir",
    "paldi",
    "railway",
    "square",
    "city",
    "nr.",
    "b/s.",
}
_MEASUREMENT_UNITS = {
    "mg/dl",
    "ng/ml",
    "mmol/l",
    "g/dl",
    "%",
    "ratio",
    "lakh",
    "million/cumm",
    "/hpf",
    "pg",
    "fl",
    "piu/ml",
    "mg/dl",
    "mm/1hr",
    "/cmm",
    "/emm",
    "million/cmm",
    "units",
}
_PHONE_MIN_DIGITS = 7


def _clean_person_span(result: RecognizerResult, text: str):
    span = text[result.start : result.end]
    if not span.strip():
        return None

    first_line = span.splitlines()[0]
    line_offset = span.find(first_line)
    working = first_line
    relative_start = line_offset

    # Remove leading whitespace inside the span line
    leading_ws = len(working) - len(working.lstrip())
    if leading_ws:
        working = working.lstrip()
        relative_start += leading_ws

    # Drop patient-label prefixes so only the actual name remains
    label_match = re.match(r"(?:patient\s+name|patient)[:\s-]*", working, flags=re.IGNORECASE)
    if label_match:
        relative_start += label_match.end()
        working = working[label_match.end():]

    leading_ws = len(working) - len(working.lstrip())
    if leading_ws:
        working = working.lstrip()
        relative_start += leading_ws

    # Remove trailing credential abbreviations (MD, MBBS, etc.)
    credential_pattern = r"(?:,?\s+(?:" + "|".join(_CREDENTIAL_WHITELIST) + r"))+\.?$"
    credential_tail = re.search(credential_pattern, working, flags=re.IGNORECASE)
    if credential_tail:
        working = working[:credential_tail.start()].rstrip()

    cleaned = working.strip(" \t,.-")
    if not cleaned:
        return None

    cleaned_offset = working.find(cleaned)
    new_start = result.start + relative_start + cleaned_offset
    result.start = new_start
    result.end = new_start + len(cleaned)
    return result


def _trim_org_span(result: RecognizerResult, text: str):
    span = text[result.start : result.end]
    if "\n" in span:
        first_line = span.splitlines()[0].strip()
        offset = span.find(first_line)
        result.start += offset
        result.end = result.start + len(first_line)
    return result


def _trim_custom_span(result: RecognizerResult, text: str) -> RecognizerResult:
    """Trim leading labels (e.g., 'UHID: ') from custom recognizer spans."""

    span = text[result.start : result.end]
    if result.entity_type == "REFERRED_BY":
        match = re.search(r"(?:Dr\.?\s+)?([A-Za-z][A-Za-z .,'-]+)", span)
    elif result.entity_type in {"UHID", "REG_NO"}:
        match = re.search(r"([A-Za-z0-9-/]+)", span)
    else:
        match = None

    if match:
        start_offset, end_offset = match.span(1)
        result.start += start_offset
        result.end = result.start + (end_offset - start_offset)

        trimmed_text = text[result.start : result.end].strip()
        if result.entity_type == "REFERRED_BY" and trimmed_text.lower() in {"referred", "referred by"}:
            return None
        if result.entity_type in {"REG_NO", "UHID"} and not any(char.isdigit() for char in trimmed_text):
            return None
    return result


def _looks_like_facility(span_text: str) -> bool:
    lowered = span_text.lower()
    return any(keyword in lowered for keyword in _FACILITY_KEYWORDS)


def _in_table_region(text: str, index: int) -> bool:
    lower_text = text.lower()
    start = lower_text.find("clinical pathology")
    end = lower_text.find("~~~ end of report ~~~")
    return start != -1 and end != -1 and start <= index <= end


def _valid_location(result: RecognizerResult, text: str) -> bool:
    span_text = text[result.start : result.end].strip()
    if not span_text:
        return False

    normalized = re.sub(r"\s+", " ", span_text.lower())
    tokens = set(normalized.replace(",", "").split())

    if tokens & _LOCATION_DENYLIST:
        return False

    # Very short tokens (<=3 chars) without digits are likely not addresses
    if len(normalized) <= 3 and not any(char.isdigit() for char in normalized):
        return False

    has_space = " " in normalized
    has_comma = "," in normalized
    has_digit = any(char.isdigit() for char in normalized)
    keyword_hit = any(keyword in normalized for keyword in _LOCATION_KEYWORDS)

    if not (has_space or has_comma or has_digit):
        return False

    if not keyword_hit and not has_digit:
        return False

    if normalized in {"new delhi", "delhi"}:
        return True

    # Reject if span contains newline immediately followed by non-alpha (likely label)
    if "\n" in span_text:
        first_line = span_text.splitlines()[0].strip()
        second_line = span_text.splitlines()[1].strip() if len(span_text.splitlines()) > 1 else ""
        if first_line.lower() in {"patient", "patient name", "name"}:
            return False
        if second_line and second_line.lower() in _LOCATION_DENYLIST:
            return False

    return True


def _valid_person(result: RecognizerResult, text: str) -> bool:
    span_text = text[result.start : result.end].strip()
    if not span_text:
        return False
    normalized = span_text.lower().replace("\n", " ").strip()
    if normalized in _LAB_DENYLIST:
        return False
    if any(token.strip() in _LAB_DENYLIST for token in normalized.split()):
        return False
    if _in_table_region(text, result.start) and len(normalized.split()) <= 2:
        # Likely table value, reject
        return False

    # Require cues or capitalized word pattern for single tokens
    if len(normalized.split()) == 1 and not normalized[0].isupper():
        return False

    context_window = 40
    pre_context = text[max(0, result.start - context_window) : result.start]
    post_context = text[result.end : result.end + context_window]
    if not _PERSON_CUES.search(pre_context + post_context) and len(normalized.split()) == 1:
        return False

    return True


def _in_measurement_context(text: str, start: int, end: int) -> bool:
    context_window = text[max(0, start - 12) : min(len(text), end + 12)].lower()
    for unit in _MEASUREMENT_UNITS:
        if unit in context_window:
            return True
    if re.search(r"\d+\.\d+", context_window):
        return True
    if re.search(r"\d+\s*-\s*\d+", context_window):
        return True
    return False


def _valid_phone(result: RecognizerResult, text: str) -> bool:
    span_text = text[result.start : result.end]
    digits = re.sub(r"\D", "", span_text)
    if len(digits) < _PHONE_MIN_DIGITS:
        return False
    if re.search(r"\d+\.\d+", span_text):  # decimal numbers -> measurement
        return False
    if _in_table_region(text, result.start) and _in_measurement_context(text, result.start, result.end):
        return False
    return True


def _drop_credential_location(result: RecognizerResult, text: str) -> bool:
    if result.entity_type != "LOCATION":
        return False
    span_text = text[result.start : result.end].strip().lower()
    if span_text in _CREDENTIAL_WHITELIST:
        return True
    pre_context = text[max(0, result.start - 10) : result.start].strip().lower()
    if pre_context.endswith((",", "mbbs", "dmlt")):
        return True
    return False


def _regex_fallback(text: str, existing_results: Iterable[RecognizerResult]) -> List[RecognizerResult]:
    occupied = [(res.start, res.end, res.entity_type) for res in existing_results]
    patterns = {
        "UHID": re.compile(r"UHID[:\s]*([A-Za-z0-9-]+)", re.IGNORECASE),
        "REFERRED_BY": re.compile(
            r"Referred By[:\s]*([A-Za-z .,'-]+?)(?:(?:\s+Date\b)|(?:\s+\d{1,2}/\d{1,2}/\d{2,4})|$)",
            re.IGNORECASE,
        ),
        "REG_NO": re.compile(
            r"Reg(?:\.|istration)?\.?\s*(?:No|Number)[:\.\s]*([A-Za-z0-9-/]+)",
            re.IGNORECASE,
        ),
        "PERSON": re.compile(
            r"Patient Name[:\s]*(?:Mr\.?|Mrs\.?|Ms\.?|Dr\.?)?\s*([A-Z][A-Za-z .'-]+)(?=\s+Age\b)",
            re.IGNORECASE,
        ),
        "LOCATION": re.compile(
            r"([A-Za-z0-9 ,'-]+(?:Road|Street|St\.|Rd\.|Avenue|Colony|Block|Lane|Nagar|Delhi|New Delhi|India)\b[ A-Za-z0-9,.-]*)",
            re.IGNORECASE,
        ),
        "PHONE_NUMBER": re.compile(
            r"(\+?\d[\d\s-]{6,}\d)",
            re.IGNORECASE,
        ),
    }

    def _overlaps(start: int, end: int) -> bool:
        for s, e, _ in occupied:
            if start < e and end > s:
                return True
        return False

    fallback_results: List[RecognizerResult] = []
    for ent_type, pattern in patterns.items():
        for match in pattern.finditer(text):
            try:
                span = match.span(1)
            except IndexError:
                span = match.span(0)
            if _overlaps(*span):
                continue
            fallback_results.append(
                RecognizerResult(entity_type=ent_type, start=span[0], end=span[1], score=0.85)
            )
    return fallback_results


def detect_pii(text: str) -> List[RecognizerResult]:
    """Run Presidio analyzer with custom recognizers and heuristics for lab reports."""

    base_entities = [
        "PERSON",
        "ORG",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "LOCATION",
        "REFERRED_BY",
        "REG_NO",
        "UHID",
    ]

    analyzer_results = analyzer.analyze(text=text, entities=base_entities, language="en")

    filtered_results: List[RecognizerResult] = []

    for result in analyzer_results:
        if result.entity_type == "PERSON" and not _valid_person(result, text):
            continue
        if result.entity_type == "LOCATION":
            if _drop_credential_location(result, text):
                continue
            if not _valid_location(result, text):
                continue
            span_text = text[result.start : result.end]
            if _looks_like_facility(span_text):
                result.entity_type = "ORG"
                result = _trim_org_span(result, text)
                filtered_results.append(result)
                continue
        if result.entity_type == "PHONE_NUMBER" and not _valid_phone(result, text):
            continue
        span_text = text[result.start : result.end]
        if result.entity_type == "PERSON" and _looks_like_facility(span_text):
            result.entity_type = "ORG"

        if result.entity_type == "PERSON":
            cleaned = _clean_person_span(result, text)
            if cleaned is None:
                continue
            result = cleaned

        if result.entity_type == "ORG":
            result = _trim_org_span(result, text)

        if result.entity_type in {"UHID", "REG_NO", "REFERRED_BY"}:
            trimmed = _trim_custom_span(result, text)
            if trimmed is None:
                continue
            result = trimmed

        filtered_results.append(result)

    fallback = _regex_fallback(text, filtered_results)
    for result in fallback:
        if result.entity_type == "PERSON":
            if not _valid_person(result, text):
                continue
            cleaned = _clean_person_span(result, text)
            if cleaned is None:
                continue
            result = cleaned
        if result.entity_type == "ORG":
            result = _trim_org_span(result, text)
        if result.entity_type == "LOCATION":
            if not _valid_location(result, text):
                continue
            span_text = text[result.start : result.end]
            if _looks_like_facility(span_text):
                result.entity_type = "ORG"
                result = _trim_org_span(result, text)
                filtered_results.append(result)
                continue
        if result.entity_type == "PHONE_NUMBER" and not _valid_phone(result, text):
            continue
        if result.entity_type in {"UHID", "REG_NO", "REFERRED_BY"}:
            trimmed = _trim_custom_span(result, text)
            if trimmed is None:
                continue
            result = trimmed
        filtered_results.append(result)

    # Deduplicate on span/entity
    unique_results: List[RecognizerResult] = []
    seen = set()
    for result in sorted(filtered_results, key=lambda r: (r.start, r.end, r.entity_type)):
        key = (result.start, result.end, result.entity_type)
        if key in seen:
            continue
        seen.add(key)
        unique_results.append(result)

    return unique_results
