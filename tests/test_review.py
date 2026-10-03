import numpy as np

from pipeline import review
from pipeline.merge import Group, Observation
from pipeline.scan import GRID_COLS, GRID_ROWS

EYE = np.eye(3)


def obs(sweep, anchor, score=0.9, text="Q01"):
    return Observation(sweep, np.zeros(3), np.array([1.0, 0, 0]), (0, 0, 1, 1), score, text, 1.0,
                       None if anchor is None else np.asarray(anchor, float))


def grid(value):
    return np.full((GRID_ROWS, GRID_COLS), value, np.float16)


def test_line_of_sight():
    assert review.line_of_sight(grid(2.0), EYE, np.zeros(3), [2.05, 0, 0])
    assert not review.line_of_sight(grid(1.0), EYE, np.zeros(3), [2.0, 0, 0])
    assert not review.line_of_sight(grid(0.0), EYE, np.zeros(3), [2.0, 0, 0])


def test_few_observations():
    g = Group([obs("sweep-01", [2, 0, 0])], np.array([2.0, 0, 0]))
    sweeps = [("sweep-01", np.zeros(3), EYE), ("sweep-02", np.array([0.0, 1.0, 0]), EYE), ("sweep-03", np.array([9.0, 0, 0]), EYE)]
    grids = {"sweep-02": grid(5.0), "sweep-03": grid(5.0)}
    assert review.few_observations(g, sweeps, grids.__getitem__)
    grids["sweep-02"] = grid(1.0)
    assert not review.few_observations(g, sweeps, grids.__getitem__)
    two = Group([obs("sweep-01", [2, 0, 0]), obs("sweep-02", [2, 0, 0])], np.array([2.0, 0, 0]))
    assert not review.few_observations(two, sweeps, {"sweep-03": grid(5.0)}.__getitem__)
    assert not review.few_observations(Group([obs("sweep-01", None)], None), sweeps, grids.__getitem__)


def test_reasons_in_contract_order():
    g = Group([obs("sweep-01", [0, 0, 0], 0.3, "Q01"), obs("sweep-02", [0.5, 0, 0], 0.4, "q02")], np.array([0.0, 0, 0]))
    assert review.reasons(g, "", 0.5, 0.2, True, True) == list(review.REASONS[:2]) + ["few_observations", "anchor_variance", "ocr_conflict", "ambiguous_cabinet"]


def test_clean_device_has_no_reasons():
    g = Group([obs("sweep-01", [0, 0, 0], text="Q01"), obs("sweep-02", [0.1, 0, 0], text="q01 "), obs("sweep-03", None, text="")],
              np.array([0.05, 0, 0]))
    assert review.reasons(g, "Q01", 0.5, 0.2, False, False) == []


def test_space_variants_are_no_ocr_conflict():
    g = Group([obs("sweep-01", [0, 0, 0], text="Q01 FEED"), obs("sweep-02", [0, 0, 0], text="q01feed")], np.zeros(3))
    assert review.reasons(g, "Q01 FEED", 0.5, 0.2, False, False) == []


def test_no_anchor():
    g = Group([obs("sweep-01", None)], None)
    assert review.reasons(g, "Q01", 0.5, 0.2, False, False) == ["no_anchor"]
