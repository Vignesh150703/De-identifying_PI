import argparse
from src.deidentify_pipeline import deidentify

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="De-identify PDFs or Images with Presidio.")
    parser.add_argument("--input", required=True, help="Path to input PDF or image file")
    parser.add_argument("--output", default="output", help="Output directory path")
    parser.add_argument("--redact-image", action="store_true", help="Enable image redaction")
    args = parser.parse_args()

    print("=== Starting De-identification Process ===")
    deidentify(args.input, args.output, args.redact_image)
    print("=== Process Completed Successfully ===")
