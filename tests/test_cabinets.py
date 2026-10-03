from pipeline.cabinets import assign


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
