from presidio_image_redactor import ImageRedactorEngine

image_redactor = ImageRedactorEngine()

def redact_image(input_image_path, output_image_path):
    """
    Redacts PII directly from images using Presidio's OCR + bounding boxes
    """
    image_redactor.redact(
        image_path=input_image_path,
        output_image_path=output_image_path
    )
    return output_image_path
