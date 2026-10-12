import pytest

from digitizer import colors as C


def test_ciede2000_reference_pairs():
    pairs = [((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
             ((50.0, 2.5, 0.0), (73.0, 25.0, -18.0), 27.1492),
             ((2.0776, 0.0795, -1.135), (0.9033, -0.0636, -0.5514), 0.9082)]
    for a, b, expected in pairs:
        assert abs(C.ciede2000(a, b) - expected) < 1e-3


def test_hex_roundtrip():
    assert C.rgb_to_hex(C.lab_to_rgb(C.hex_to_lab("#3953a4"))) == "#3953a4"
    assert C.normalize_hex("ABC") == "#aabbcc"


def test_auto_group_threshold_merges_near_shades():
    areas = {"#e02020": 10, "#e22424": 5, "#2060d0": 8, "#2262d2": 3, "#ffd700": 4}
    log = []
    groups = C.auto_group(areas, 8.0, None, 25.0, [], log)
    assert len(groups) == 3
    members = sorted(sorted(g.members) for g in groups)
    assert ["#2060d0", "#2262d2"] in members and ["#e02020", "#e22424"] in members


def test_colors_n_merges_closest_and_refuses_clearly_different():
    areas = {"#e02020": 10, "#e84040": 5, "#2060d0": 8, "#ffd700": 4}
    log = []
    groups = C.auto_group(areas, 2.0, 3, 25.0, [], log)      # low threshold: nothing merges automatically
    assert len(groups) == 3                                   # reds (dE ~ 10) merged to reach N=3
    with pytest.raises(C.GroupingDecisionNeeded):
        C.auto_group(areas, 2.0, 2, 25.0, [], [])             # blue vs red/yellow is far over 25


def test_manual_groups_override_and_skip():
    areas = {"#e02020": 10, "#e22424": 5, "#2060d0": 8, "#fcfcfb": 50}
    manual = C.parse_group_args(["#e02020=brand red", "#fcfcfb=skip"])
    groups = C.auto_group(areas, 8.0, None, 25.0, manual, [])
    by_name = {g.name: g for g in groups}
    assert by_name["brand red"].members == ["#e02020"] and by_name["brand red"].manual
    assert by_name["skip"].skip
    assert "#e22424" not in by_name["brand red"].members   # manual entries are exact


def test_thread_matching_uses_shipped_palettes():
    pal = C.load_palettes(["InkStitch Madeira Polyneon", "InkStitch Isacord Polyester"])
    assert all(len(v) > 300 for v in pal.values())
    best = C.nearest_threads("#000000", pal)
    assert best and best[0]["delta_e"] < 3
