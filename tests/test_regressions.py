import pytest

from src.pii_detector import detect_pii


def _entities(text, entity_type):
    return [
        (res.start, res.end, text[res.start : res.end])
        for res in detect_pii(text)
        if res.entity_type == entity_type
    ]


def test_address_detected_as_location():
    sample = "Hospital Road, New Delhi\nCall 011-03849283"
    locations = _entities(sample, "LOCATION")
    assert any("Hospital Road" in span for _, _, span in locations)


def test_patient_label_not_marked_location():
    sample = "Patient Name: Mr. Dummy Age / Sex: 23 YRS/M"
    locations = _entities(sample, "LOCATION")
    assert not any("patient" in span.lower() for _, _, span in locations)


@pytest.mark.parametrize(
    "line",
    [
        "LDL / HDL 0.64 1.5-3.5",
        "Serum Triiodothyronine, T3 2.10 ng/mL",
    ],
)
def test_measurements_not_flagged_as_phone(line):
    phones = _entities(line, "PHONE_NUMBER")
    assert not phones


def test_contact_number_flagged_as_phone():
    sample = "For details call us on 011-03849283 or visit Hospital Road, New Delhi"
    phones = _entities(sample, "PHONE_NUMBER")
    assert any("03849283" in span for _, _, span in phones)

