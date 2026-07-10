"""Acceptable-C-range vs. number-of-vessels plot (paper Fig. 8/9 style)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .results import OptimizationResults  # noqa: E402


def plot_acceptable_range(
    results: OptimizationResults,
    path: Path,
    *,
    c_unit: str = "",
) -> Path:
    """Render the acceptable C-range as a function of the number of vessels.

    Draws the lower- and upper-bound C-value lines, shades the feasible band
    between them, and marks the minimum feasible number of vessels.

    Args:
        results: Aggregated optimization results.
        path: Output image path (extension selects the format, e.g. ``.png``).
        c_unit: Optional unit label for the C-value axis (e.g. ``"J"``).

    Returns:
        The path the figure was written to.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    n_values = [v.n_vessels for v in results.vessels]
    c_lower = [v.c_lower if v.c_lower is not None else float("nan") for v in results.vessels]
    c_upper = [v.c_upper if v.c_upper is not None else float("nan") for v in results.vessels]

    fig, ax = plt.subplots(figsize=(8, 5))

    feasible_n = [v.n_vessels for v in results.vessels if v.feasible]
    feasible_lower = [
        v.c_lower for v in results.vessels if v.feasible and v.c_lower is not None
    ]
    feasible_upper = [
        v.c_upper for v in results.vessels if v.feasible and v.c_upper is not None
    ]

    ax.plot(n_values, c_lower, marker="o", color="#0D38E0", label="Lower acceptable C")
    ax.plot(n_values, c_upper, marker="s", color="#FF960D", label="Upper acceptable C")

    if feasible_n:
        ax.fill_between(
            feasible_n,
            feasible_lower,
            feasible_upper,
            color="#00E6A1",
            alpha=0.25,
            label="Acceptable range",
        )

    if results.min_feasible_vessels is not None:
        ax.axvline(
            results.min_feasible_vessels,
            color="#000000",
            linestyle="--",
            linewidth=1.0,
            label=f"Min. feasible = {results.min_feasible_vessels}",
        )

    ax.set_xlabel("Number of surge vessels")
    ylabel = "C-value" + (f" [{c_unit}]" if c_unit else "")
    ax.set_ylabel(ylabel)
    ax.set_title("Acceptable C-value range vs. number of surge vessels")
    if n_values:
        ax.set_xticks(n_values)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path
