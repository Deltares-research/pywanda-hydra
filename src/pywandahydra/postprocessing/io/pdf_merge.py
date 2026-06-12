"""Utilities for merging per-case figure PDFs into one run-level PDF."""

from __future__ import annotations

import logging
from pathlib import Path

from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)


def merge_case_figure_pdfs(
    scenarios_dir: Path,
    output_path: Path,
) -> Path | None:
    """Merge all per-case figure PDFs into a single PDF.

    The merge order is deterministic:
    1. Case directories sorted by name.
    2. PDF files inside each case's ``figures/`` directory sorted by name.

    Args:
        scenarios_dir: Path to the run's ``scenarios/`` directory.
        output_path: Target merged PDF path.

    Returns:
        Path to the merged PDF, or None when no source PDFs are found.
    """
    if not scenarios_dir.exists() or not scenarios_dir.is_dir():
        logger.warning("Scenarios directory not found for PDF merge: %s", scenarios_dir)
        return None

    source_pdfs: list[Path] = []
    for case_dir in sorted(p for p in scenarios_dir.iterdir() if p.is_dir()):
        figures_dir = case_dir / "figures"
        if not figures_dir.exists() or not figures_dir.is_dir():
            continue
        source_pdfs.extend(sorted(figures_dir.glob("*.pdf")))

    if not source_pdfs:
        logger.info("No per-case figure PDFs found; skipping merged PDF generation.")
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()

    for pdf_path in source_pdfs:
        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            writer.add_page(page)

    with output_path.open("wb") as merged_file:
        writer.write(merged_file)

    logger.info("Merged %d PDF files into %s", len(source_pdfs), output_path)
    return output_path
