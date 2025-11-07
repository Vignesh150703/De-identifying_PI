from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

anonymizer = AnonymizerEngine()


def anonymize_text(text, analyzer_results):
    # Build OperatorConfig objects so the AnonymizerEngine receives the
    # expected types (not plain dicts). Use from_json for convenience.
    operators = {
        "DEFAULT": OperatorConfig.from_json({"type": "mask", "masking_char": "*", "chars_to_mask": 0}),
        "PERSON": OperatorConfig.from_json({"type": "replace", "new_value": "[NAME]"}),
        "EMAIL_ADDRESS": OperatorConfig.from_json({"type": "replace", "new_value": "[EMAIL]"}),
        "PHONE_NUMBER": OperatorConfig.from_json({"type": "replace", "new_value": "[PHONE]"}),
        "LOCATION": OperatorConfig.from_json({"type": "replace", "new_value": "[LOCATION]"}),
    }

    # Add operator configs for custom fields we detect via regex
    operators.update({
        "REFERRED_BY": OperatorConfig.from_json({"type": "replace", "new_value": "[REFERRED_BY]"}),
        "REG_NO": OperatorConfig.from_json({"type": "replace", "new_value": "[REG_NO]"}),
        "UHID": OperatorConfig.from_json({"type": "replace", "new_value": "[UHID]"}),
        "ORG": OperatorConfig.from_json({"type": "replace", "new_value": "[ORG]"}),
    })

    return anonymizer.anonymize(
        text=text,
        analyzer_results=analyzer_results,
        operators=operators,
    ).text

