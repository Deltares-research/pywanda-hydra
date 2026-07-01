"""Run-level step: merge per-case route PDFs into one run artifact."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..core.context import PostProcessingRunContext
from ..io.pdf_merge import merge_case_figure_pdfs


class MergePdfsStep:
    name = "merge_pdfs"

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")

    def __init__(self, params: Params | None = None) -> None:
        self._p = params or self.Params()

    def run(self, ctx: PostProcessingRunContext) -> None:
        scenarios_dir = ctx.run_root / "scenarios"
        merged_pdf = ctx.run_root / "figures" / f"{ctx.run_id}_merged.pdf"
        merge_case_figure_pdfs(scenarios_dir, merged_pdf)
