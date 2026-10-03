import numpy as np

from pipeline.merge import Observation, merge, ray_distance, text_key, vote_text

ORIGIN = np.zeros(3)


def obs(anchor, score=0.5, text="", text_score=1.0, sweep="sweep-01", origin=ORIGIN, ray=(1.0, 0.0, 0.0)):
    return Observation(sweep, np.asarray(origin, float), np.asarray(ray, float), (0, 0, 1, 1), score, text, text_score,
                       None if anchor is None else np.asarray(anchor, float))


def test_single_linkage_chains_and_takes_median_and_max_score():
    a = [obs([0, 0, 0], 0.2), obs([0.15, 0, 0], 0.9), obs([0.3, 0, 0], 0.4), obs([5, 0, 0], 0.7)]
    groups = sorted(merge(a, 0.2), key=lambda g: g.anchor[0])
    assert len(groups) == 2
    assert np.allclose(groups[0].anchor, [0.15, 0, 0])
    assert groups[0].score == 0.9 and len(groups[0].observations) == 3
    assert np.allclose(groups[1].anchor, [5, 0, 0])


def test_median_is_component_wise():
    a = [obs([0, 0, 0]), obs([0.1, 0.1, 0]), obs([0.05, 0.0, 0.1])]
    (g,) = merge(a, 0.2)
    assert np.allclose(g.anchor, [0.05, 0.0, 0.0])


def test_unanchored_joins_nearest_ray_group():
    near = obs([3, 0.1, 0])
    far = obs([3, 1.0, 0])
    ray = obs(None, sweep="sweep-02")
    groups = merge([near, far, ray], 0.2)
    assert len(groups) == 2
    joined = next(g for g in groups if ray in g.observations)
    assert near in joined.observations and joined.sweeps == {"sweep-01", "sweep-02"}


def test_unanchored_behind_or_far_becomes_own_group():
    behind = obs([-3, 0, 0])
    lone = obs(None)
    groups = merge([behind, lone], 0.2)
    assert len(groups) == 2
    assert any(g.anchor is None and g.observations == [lone] for g in groups)
    assert ray_distance(ORIGIN, np.array([1.0, 0, 0]), np.array([-3.0, 0, 0])) == np.inf


def test_vote_text_is_score_weighted_and_normalized():
    a = [obs([0, 0, 0], text="H03  metering", text_score=0.6), obs([0, 0, 0], text="H03 METERING", text_score=0.5),
         obs([0, 0, 0], text="H08 METERING", text_score=0.9), obs([0, 0, 0], text="", text_score=1.0)]
    assert vote_text(a) == "H03 metering"
    assert vote_text([obs([0, 0, 0])]) == ""


def test_vote_text_counts_sweeps_and_keeps_the_spaced_variant():
    a = [obs([0, 0, 0], text="H04 SOLAR1", text_score=0.9, sweep="sweep-12"), obs([0, 0, 0], text="H04 SOLAR 1", text_score=0.6, sweep="sweep-13"),
         obs([0, 0, 0], text="KOKOOJA WISKO", text_score=0.99, sweep="sweep-12"), obs([0, 0, 0], text="KOKOOJA WISKO", text_score=0.99, sweep="sweep-12")]
    assert vote_text(a) == "H04 SOLAR 1"
    assert text_key(" H04 Solar 1 ") == "h04solar1"


def test_empty_input():
    assert merge([], 0.2) == []
