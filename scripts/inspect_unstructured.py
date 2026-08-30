"""Run the temporary Unstructured inspector and write readable output to a text file.

Usage:
    python scripts/inspect_unstructured.py /path/to/document.pdf

The script writes to `unstructured_text_output_text` at the repository root.
"""
import sys
from pathlib import Path

OUTPUT_NAME = "unstructured_text_output_text"


def element_to_text(e) -> str:
    content = getattr(e, "page_content", None)
    # metadata might be a dict or an object
    md = getattr(e, "metadata", None)
    return f"content:\n{content}\nmetadata:\n{md}\n\n"


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/inspect_unstructured.py /path/to/document.pdf")
        sys.exit(2)

    file_path = sys.argv[1]
    repo_root = Path(__file__).resolve().parents[1]
    out_path = repo_root / OUTPUT_NAME

    try:
        from src.infrastructure.ingestion.document_loader import inspect_raw_unstructured_elements
    except Exception as exc:
        print("Failed to import inspector:", exc)
        sys.exit(1)

    try:
        elements = inspect_raw_unstructured_elements(file_path)
    except Exception as exc:
        print("Failed to load elements:", exc)
        sys.exit(1)

    with out_path.open("w", encoding="utf-8") as f:
        if not elements:
            f.write("<no elements returned>\n")
        else:
            for i, e in enumerate(elements, 1):
                f.write(f"--- Element {i} ---\n")
                f.write(element_to_text(e))

    print(f"Wrote inspection output to: {out_path}")


if __name__ == "__main__":
    main()
