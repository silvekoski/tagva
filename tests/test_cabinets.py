import numpy as np

from pipeline.cabinets import agrees, assign, confirmed
from pipeline.merge import Group, Observation
from pipeline.scan import GRID_COLS, GRID_ROWS


def test_nearest_label_in_3d():
    labels = [(0, 0, 1.2), (0, 1, 1.2), (0, 3, 1.2)]
    assert assign([(0, 0.1, 1.8)], labels, 2.0) == [(0, False)]


def test_horizontal_fallback_when_label_is_high():
    labels = [(0, 0, 4.5)]
    assert assign([(0, 0.5, 1.8)], labels, 2.0) == [(0, False)]
    assert assign([(0, 2.5, 1.8)], labels, 2.0) == [(None, False)]


def test_ambiguous_when_second_is_within_20_percent():
    labels = [(0, -0.5, 1.2), (0, 0.55, 1.2)]
    assert assign([(0, 0, 1.2)], labels, 2.0) == [(0, True)]
    labels = [(0, -0.5, 1.2), (0, 0.65, 1.2)]
    assert assign([(0, 0, 1.2)], labels, 2.0) == [(0, False)]


def test_unassigned_and_missing_anchors():
    labels = [None, (0, 0, 1.2)]
    assert assign([None, (0, 0, 1.0), (10, 0, 1.0)], labels, 2.0) == [(None, False), (1, False), (None, False)]
    assert assign([(0, 0, 1.0)], [], 2.0) == [(None, False)]


def obs(sweep, text, anchor=(2.0, 0.0, 0.0), origin=(0.0, 0.0, 0.0)):
    return Observation(sweep, np.asarray(origin, float), np.array([1.0, 0.0, 0.0]), (0, 0, 1, 1), 0.9, text, 0.9, np.asarray(anchor, float))


def grid(value):
    return np.full((GRID_ROWS, GRID_COLS), value, np.float16)


SWEEPS = [("sweep-01", np.zeros(3), np.eye(3)), ("sweep-02", np.array([0.0, 1.0, 0.0]), np.eye(3))]


def test_agrees_ignores_spaces_case_and_ocr_confusions():
    assert agrees("H02 STATIONTRANSFORMER", "h02 station transformer")
    assert agrees("0T1", "OT1") and agrees("H01 PTI", "H01 PT1")
    assert agrees("KOKOOJA WISKO", "KOKOOJA KISKO")
    assert not agrees("071", "OT1") and not agrees("AS", "AR") and not agrees("H03", "H04")


def test_confirmed_needs_two_sweeps_when_others_see_the_label():
    anchor = np.array([2.0, 0.0, 0.0])
    sees = {"sweep-01": grid(5.0), "sweep-02": grid(5.0)}.__getitem__
    blind = {"sweep-01": grid(5.0), "sweep-02": grid(0.5)}.__getitem__
    assert confirmed(Group([obs("sweep-01", "H03 METERING"), obs("sweep-02", "H03METERING")], anchor), SWEEPS, sees)
    note = Group([obs("sweep-01", "EI MOMENTISSA"), obs("sweep-02", "ME MEPNSSA")], anchor)
    assert not confirmed(note, SWEEPS, sees)
    assert not confirmed(Group([obs("sweep-01", "OT1")], anchor), SWEEPS, sees)
    assert confirmed(Group([obs("sweep-01", "OT1")], anchor), SWEEPS, blind)
    far = Group([obs("sweep-01", "OT1", anchor=(9.0, 0, 0))], np.array([9.0, 0, 0]))
    assert not confirmed(far, SWEEPS, blind)
    assert not confirmed(Group([obs("sweep-01", "")], anchor), SWEEPS, blind)
    assert not confirmed(Group([obs("sweep-01", "OT1")], None), SWEEPS, blind)
