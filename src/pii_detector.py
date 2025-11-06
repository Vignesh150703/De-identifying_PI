from presidio_analyzer import AnalyzerEngine
import re

analyzer = AnalyzerEngine()


class _SimpleResult:
    """Small shim to mimic RecognizerResult objects used by the pipeline.

    Attributes: entity_type, start, end, score
    """

    def __init__(self, entity_type, start, end, score=0.85):
        self.entity_type = entity_type
        self.start = start
        self.end = end
        self.score = score


def _find_custom_entities(text):
    """Find custom PII-like entities (UHID, Referred By, Reg. no) via regex.

    Returns a list of _SimpleResult instances.
    """
    patterns = {
        "UHID": r"UHID[:\s]*([A-Za-z0-9-]+)",
        "REFERRED_BY": r"Referred By[:\s]*([A-Za-z .,-]+)",
        # Accept many label variants for registration number
        "REG_NO": r"Reg(?:\.|istration)?\.?\s*(?:no|number)[:\.\s]*([A-Za-z0-9-/]+)",
    }
    found = []
    for ent_type, pat in patterns.items():
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            try:
                span = m.span(1)
                val = m.group(1)
            except IndexError:
                span = m.span(0)
                val = m.group(0)
            found.append(_SimpleResult(ent_type, span[0], span[1], score=0.9))
    return found


def detect_pii(text):
    """Run Presidio analyzer for common entities then append custom regex-based entities.

    Returns a list of RecognizerResult-like objects (original Presidio results plus _SimpleResult)
    so the rest of the pipeline can treat them uniformly.
    """
    results = analyzer.analyze(
        text=text,
        entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION","REFERRED_BY","REG_NO","UHID"],
        language="en",
    )

    # Append custom regex-based detections
    custom = _find_custom_entities(text)
    results.extend(custom)
    return results
