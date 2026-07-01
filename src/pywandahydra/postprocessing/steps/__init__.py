"""Post-processing steps — pluggable submodules for the pipeline.

Each module in this package implements one post-processing step.
"""

from .aggregate_tables import AggregateTablesStep
from .merge_pdfs import MergePdfsStep
from .plot_report import PlotReportStep
from .summary_table import SummaryTableStep

__all__ = [
    "AggregateTablesStep",
    "MergePdfsStep",
    "PlotReportStep",
    "SummaryTableStep",
]
