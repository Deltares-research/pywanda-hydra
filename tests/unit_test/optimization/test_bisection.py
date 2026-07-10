"""Tests for the bisection boundary search."""

from __future__ import annotations

import pytest

from pywandahydra.optimization.bisection import find_boundary


def test_lower_bound_when_low_end_rejected() -> None:
    # Acceptable when c >= 12  -> low end rejected, high end accepted.
    result = find_boundary(lambda c: c >= 12.0, 1.0, 30.0, rel_tol=0.001, max_iter=50)
    assert result.bound_type == "lower"
    assert result.boundary is not None
    assert result.boundary == pytest.approx(12.0, abs=0.1)
    assert result.converged
    # Boundary is on the acceptable side (conservative).
    assert result.boundary >= 12.0


def test_upper_bound_when_high_end_rejected() -> None:
    # Acceptable when c <= 13 -> high end rejected, low end accepted.
    result = find_boundary(lambda c: c <= 13.0, 1.0, 30.0, rel_tol=0.001, max_iter=50)
    assert result.bound_type == "upper"
    assert result.boundary is not None
    assert result.boundary == pytest.approx(13.0, abs=0.1)
    assert result.boundary <= 13.0


def test_all_acceptable() -> None:
    result = find_boundary(lambda c: True, 1.0, 30.0)
    assert result.bound_type == "all_acceptable"
    assert result.boundary is None
    assert result.iterations == 0


def test_none_acceptable() -> None:
    result = find_boundary(lambda c: False, 1.0, 30.0)
    assert result.bound_type == "none_acceptable"
    assert result.boundary is None


def test_invalid_bracket_raises() -> None:
    with pytest.raises(ValueError, match="lower must be strictly less than upper"):
        find_boundary(lambda c: True, 5.0, 5.0)


def test_respects_max_iter() -> None:
    result = find_boundary(lambda c: c >= 15.0, 1.0, 30.0, rel_tol=1e-12, max_iter=3)
    assert result.iterations == 3
    assert not result.converged
    # Every probe is recorded (2 endpoints + iterations).
    assert len(result.evaluations) == 2 + 3
