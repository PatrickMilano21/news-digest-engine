#!/usr/bin/env python
"""Extract text from a .docx file and print to stdout."""
from __future__ import annotations

import sys

def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/read_docx.py <path.docx>", file=sys.stderr)
        return 1

    path = sys.argv[1]

    try:
        from docx import Document
    except ImportError:
        print("Missing dependency. Run: pip install python-docx", file=sys.stderr)
        return 1

    doc = Document(path)
    for para in doc.paragraphs:
        print(para.text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
