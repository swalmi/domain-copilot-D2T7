"""Run a standalone hi_res inspector using `unstructured.partition.pdf.partition_pdf`.

Usage:
    python scripts/inspect_unstructured_hires.py /path/to/document.pdf

Writes output to `unstructured_text_output_text` in the repo root.
"""
import sys
from pathlib import Path

OUTPUT_NAME = "unstructured_text_output_text"


def element_to_text(e) -> str:
    # Unstructured Elements vary by version; try common attributes
    text = getattr(e, "text", None) or getattr(e, "page_content", None) or getattr(e, "content", None)
    md = getattr(e, "metadata", None) or getattr(e, "element_metadata", None) or {}
    return f"content:\n{text}\nmetadata:\n{md}\n\n"


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/inspect_unstructured_hires.py /path/to/document.pdf")
        sys.exit(2)

    file_path = sys.argv[1]
    repo_root = Path(__file__).resolve().parents[1]
    out_path = repo_root / OUTPUT_NAME

    try:
        from unstructured.partition.pdf import partition_pdf
    except Exception as exc:
        print("Failed to import unstructured.partition.pdf:", exc)
        sys.exit(1)

    try:
        elements = partition_pdf(filename=file_path, strategy="hi_res")
    except Exception as exc:
        print("Partition hi_res failed:", exc)
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
