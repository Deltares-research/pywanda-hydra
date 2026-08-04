"""Run-level figure PDF assembly."""

from __future__ import annotations

import logging
from pathlib import Path

from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)


def merge_case_figure_pdfs(scenarios_dir: Path, output_path: Path) -> Path | None:
    """Merge case PDFs in deterministic case and filename order."""
    if not scenarios_dir.is_dir():
        logger.warning("Scenarios directory not found for PDF merge: %s", scenarios_dir)
        return None

    source_pdfs = [
        pdf_path
        for case_dir in sorted(path for path in scenarios_dir.iterdir() if path.is_dir())
        if (figures_dir := case_dir / "figures").is_dir()
        for pdf_path in sorted(figures_dir.glob("*.pdf"))
    ]
    if not source_pdfs:
        logger.info("No per-case figure PDFs found; skipping merged PDF generation.")
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    for pdf_path in source_pdfs:
        for page in PdfReader(str(pdf_path)).pages:
            writer.add_page(page)
    with output_path.open("wb") as merged_file:
        writer.write(merged_file)
    logger.info("Merged %d PDF files into %s", len(source_pdfs), output_path)
    return output_path
