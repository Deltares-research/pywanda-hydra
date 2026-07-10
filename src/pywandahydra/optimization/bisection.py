"""Bisection boundary search (Zwan et al. 2012, §4.3).

Given a boolean *acceptability* predicate over a C-value bracket, this module
locates the C-value at the acceptability boundary using the bisection routine
described in the paper::

    C_new = (C_old + C_prev) / 2

where ``C_prev`` stores one *acceptable* and one *not-acceptable* bound. Each
iteration halves the interval between the acceptable and the rejected bound and
continues until the new value deviates less than a relative tolerance from the
previous one.

The routine also reports *which side* of the boundary is acceptable so the
optimizer can translate a criterion into either a lower or an upper bound on the
C-value:

* acceptable at the low end, rejected at the high end -> the criterion imposes an
  **upper** bound (acceptable region is ``C <= boundary``);
* rejected at the low end, acceptable at the high end -> the criterion imposes a
  **lower** bound (acceptable region is ``C >= boundary``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

BoundType = Literal["lower", "upper", "all_acceptable", "none_acceptable"]


@dataclass(frozen=True)
class BisectionResult:
    """Outcome of a boundary bisection search.

    Attributes:
        boundary: The C-value at the acceptability boundary (conservative:
            the acceptable side). ``None`` when no boundary lies inside the
            bracket (criterion is satisfied or violated across the whole range).
        bound_type: How the criterion constrains the C-value. ``"lower"`` or
            ``"upper"`` when a boundary exists; ``"all_acceptable"`` when the
            criterion holds across the whole bracket; ``"none_acceptable"`` when
            it never holds.
        converged: Whether the relative-tolerance stop criterion was reached.
        iterations: Number of bisection iterations performed.
        evaluations: Ordered ``(c_value, acceptable)`` pairs that were probed.
    """

    boundary: float | None
    bound_type: BoundType
    converged: bool
    iterations: int
    evaluations: list[tuple[float, bool]] = field(default_factory=list)


def find_boundary(
    predicate: Callable[[float], bool],
    lower: float,
    upper: float,
    *,
    rel_tol: float = 0.01,
    max_iter: int = 20,
) -> BisectionResult:
    """Locate the acceptability boundary of ``predicate`` within ``[lower, upper]``.

    Args:
        predicate: Callable returning ``True`` when a C-value is acceptable.
        lower: Lower bound of the C-value bracket (must be < ``upper``).
        upper: Upper bound of the C-value bracket.
        rel_tol: Stop when ``|c_new - c_old| / |c_old| < rel_tol``.
        max_iter: Maximum number of bisection iterations.

    Returns:
        A :class:`BisectionResult`.

    Raises:
        ValueError: If ``lower`` is not strictly less than ``upper``.
    """
    if not lower < upper:
        raise ValueError("lower must be strictly less than upper")

    evaluations: list[tuple[float, bool]] = []

    def probe(c: float) -> bool:
        acceptable = bool(predicate(c))
        evaluations.append((c, acceptable))
        return acceptable

    acc_lower = probe(lower)
    acc_upper = probe(upper)

    if acc_lower == acc_upper:
        bound_type: BoundType = "all_acceptable" if acc_lower else "none_acceptable"
        return BisectionResult(
            boundary=None,
            bound_type=bound_type,
            converged=True,
            iterations=0,
            evaluations=evaluations,
        )

    # One end acceptable, the other not: the boundary lies inside the bracket.
    # "lower" bound  => acceptable region is C >= boundary (low end rejected).
    # "upper" bound  => acceptable region is C <= boundary (high end rejected).
    bound_type = "upper" if acc_lower else "lower"

    c_acc = lower if acc_lower else upper
    c_rej = upper if acc_lower else lower

    c_old = c_acc
    iterations = 0
    converged = False
    for _ in range(max_iter):
        iterations += 1
        c_new = 0.5 * (c_acc + c_rej)
        if probe(c_new):
            c_acc = c_new
        else:
            c_rej = c_new
        denom = abs(c_old) if c_old != 0.0 else 1.0
        if abs(c_new - c_old) / denom < rel_tol:
            converged = True
            c_old = c_new
            break
        c_old = c_new

    return BisectionResult(
        boundary=c_acc,
        bound_type=bound_type,
        converged=converged,
        iterations=iterations,
        evaluations=evaluations,
    )
