try:
    from presidio_image_redactor import ImageRedactorEngine  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    ImageRedactorEngine = None  # type: ignore


def redact_image(input_image_path, output_image_path):
    """Redact PII directly from images when Presidio image redactor is available."""

    if ImageRedactorEngine is None:
        raise ImportError(
            "presidio_image_redactor is not installed. Install it to enable image redaction."
        )

    engine = ImageRedactorEngine()
    engine.redact(image_path=input_image_path, output_image_path=output_image_path)
    return output_image_path
