"""Tests for the optimizer loop and criterion combination."""

from __future__ import annotations

from pywandahydra.optimization import optimizer as optimizer_module
from pywandahydra.optimization.evaluator import EvaluationResult
from pywandahydra.optimization.optimizer import _optimize_vessel, optimize

from .conftest import SyntheticEvaluator, make_config


def test_finds_minimum_feasible_vessel_count(config, synthetic_evaluator) -> None:
    results = optimize(config, synthetic_evaluator)

    # Thresholds cross at n >= 8 (see SyntheticEvaluator docstring).
    assert results.min_feasible_vessels == 8
    assert len(results.vessels) == 10

    infeasible = {v.n_vessels for v in results.vessels if not v.feasible}
    feasible = {v.n_vessels for v in results.vessels if v.feasible}
    assert infeasible == {1, 2, 3, 4, 5, 6, 7}
    assert feasible == {8, 9, 10}


def test_bounds_direction(config, synthetic_evaluator) -> None:
    results = optimize(config, synthetic_evaluator)
    v8 = next(v for v in results.vessels if v.n_vessels == 8)
    # Pressure imposes a lower bound (~12), water level an upper bound (~13).
    assert v8.pressure.bound_type == "lower"
    assert v8.water_level.bound_type == "upper"
    assert v8.c_lower is not None
    assert v8.c_upper is not None
    assert v8.c_lower <= v8.c_upper


def test_no_feasible_when_thresholds_never_cross() -> None:
    # Restrict the vessel range so the crossing (n>=8) never occurs.
    cfg = make_config(number_of_vessels={"min": 1, "max": 5, "step": 1})
    results = optimize(cfg, SyntheticEvaluator())
    assert results.min_feasible_vessels is None
    assert all(not v.feasible for v in results.vessels)


def test_memoization_reuses_evaluations(config) -> None:
    ev = SyntheticEvaluator()
    optimize(config, ev)
    calls_first = ev.calls

    ev2 = SyntheticEvaluator()
    # Wrap so repeated identical triples would be visible; the optimizer memo
    # should prevent duplicate calls within a run.
    optimize(config, ev2)
    assert ev2.calls == calls_first
    assert ev2.calls > 0


class _DrainageEvaluator:
    """Evaluator where the vessel drains (empties) at high C.

    Mirrors the real WANDA behaviour observed in the run data:

    * pressure improves monotonically with C and becomes acceptable at ``C >= 10``;
    * water level worsens with C and is acceptable only for ``C <= 15``;
    * at ``C >= 20`` the vessel drains, which the evaluator reports (as
      ``WandaEvaluator`` does) with ``min_pressure = +inf`` (pressure acceptable)
      and ``min_water_level = -inf`` (water level unacceptable).

    Without the drainage/pressure fix the high-C bracket endpoint (drained) would
    make the pressure criterion look rejected at both ends → ``none_acceptable``.
    """

    def run(self, n_vessels: int, c_value: float, laplace: float) -> EvaluationResult:
        if c_value >= 20.0:
            return EvaluationResult(
                n_vessels=n_vessels,
                c_value=c_value,
                laplace=laplace,
                min_pressure=float("inf"),
                min_water_level=float("-inf"),
                failed=True,
                error="AIRVin A1 Empty",
            )
        return EvaluationResult(
            n_vessels=n_vessels,
            c_value=c_value,
            laplace=laplace,
            min_pressure=c_value - 10.0,
            min_water_level=15.0 - c_value,
        )


def test_drainage_does_not_break_pressure_criterion() -> None:
    cfg = make_config(
        number_of_vessels={"min": 1, "max": 1, "step": 1},
        c_value={"lower": 1.0, "upper": 30.0},
        acceptance={"min_pressure": 0.0, "min_water_level": 0.0},
    )

    results = optimize(cfg, _DrainageEvaluator())
    v = results.vessels[0]

    # The drained high-C endpoint must NOT collapse the pressure criterion to
    # none_acceptable: pressure still yields a proper lower bound (~10).
    assert v.pressure.bound_type == "lower"
    assert v.pressure.boundary is not None
    assert abs(v.pressure.boundary - 10.0) < 0.5
    # Water level still yields an upper bound (~15) and the range is feasible.
    assert v.water_level.bound_type == "upper"
    assert v.c_lower is not None
    assert v.c_upper is not None
    assert v.c_lower <= v.c_upper
    assert v.feasible is True


def test_optimize_vessel_matches_single_count(config) -> None:
    # _optimize_vessel for n=8 must match the vessel result from a full run.
    full = optimize(config, SyntheticEvaluator())
    v8_full = next(v for v in full.vessels if v.n_vessels == 8)

    v8_direct = _optimize_vessel(config, SyntheticEvaluator(), 8)
    assert v8_direct.n_vessels == 8
    assert v8_direct.feasible == v8_full.feasible
    assert v8_direct.pressure.bound_type == v8_full.pressure.bound_type
    assert v8_direct.water_level.bound_type == v8_full.water_level.bound_type
    assert v8_direct.c_lower == v8_full.c_lower
    assert v8_direct.c_upper == v8_full.c_upper


def test_parallel_matches_serial(config, monkeypatch) -> None:
    # Run n_workers=1 (serial) as the reference.
    serial = optimize(config, SyntheticEvaluator())

    # Replace the process pool with a deterministic serial implementation so the
    # parallel branch is exercised without relying on spawn-pickling in pytest.
    def fake_parallel_map(func, cfg, evaluator, counts, n_workers):
        return [func(cfg, evaluator, n) for n in counts]

    monkeypatch.setattr(optimizer_module, "_parallel_map", fake_parallel_map)

    parallel_cfg = make_config(n_workers=4)
    parallel = optimize(parallel_cfg, SyntheticEvaluator())

    assert parallel.min_feasible_vessels == serial.min_feasible_vessels
    assert [v.n_vessels for v in parallel.vessels] == [v.n_vessels for v in serial.vessels]
    for pv, sv in zip(parallel.vessels, serial.vessels, strict=True):
        assert pv.feasible == sv.feasible
        assert pv.c_lower == sv.c_lower
        assert pv.c_upper == sv.c_upper
