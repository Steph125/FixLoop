"""Journal des coûts (spec/05-session-server, SRV-T2).

Aucun réseau : CostLog écrit dans un dossier temporaire. Tarifs : table de
`steering/tech.md` section 3 (estimations, la vérification se fait sur la page Usage).
"""

import pytest

from fixloop.costs import PRICES, CostLog


def log(tmp_path):
    return CostLog(root=tmp_path / "costs")


def test_sam_image_360_costs_90_cents(tmp_path):
    costs = log(tmp_path)
    assert costs.add("sam-3.1", "image", 360, 12.0, True) == pytest.approx(0.90)  # SRV-R8.1
    assert costs.day_total() == pytest.approx(0.90)


def test_sam_video_bills_at_least_50_images(tmp_path):
    costs = log(tmp_path)
    assert costs.add("sam-3.1", "video", 10, 3.0, True) == pytest.approx(0.01)  # PERC-R7.2
    assert costs.add("sam-3.1", "video", 120, 9.0, True) == pytest.approx(0.024)


def test_spark_wonder_transcribe_and_estimated_flag(tmp_path):
    costs = log(tmp_path)
    assert costs.add("muse-spark-1.3", "in", 1500, 2.0, True, estimated=True) == pytest.approx(0.001875)
    assert costs.add("muse-spark-1.3", "out", 200, 0.0, True, estimated=True) == pytest.approx(0.00085)
    assert costs.add("muse-wonder-1.0", "in", 500, 1.0, True) == pytest.approx(0.002)
    assert costs.add("muse-wonder-1.0", "out", 50, 0.0, True) == pytest.approx(0.001)
    assert costs.add("muse-voice-transcribe-1.0", "second", 30, 30.0, True) == pytest.approx(0.0015)

    by = costs.by_model()
    assert by["muse-spark-1.3"] == pytest.approx(
        costs.day_total() - by["muse-wonder-1.0"] - by["muse-voice-transcribe-1.0"])
    assert costs.entries[-1]["estimated"] is False  # pas de jetons estimés ici


def test_session_total_and_persistence(tmp_path):
    costs = log(tmp_path)
    costs.add("sam-3.1", "image", 2, 1.0, True, session_id="s1")
    costs.add("sam-3.1", "image", 4, 1.0, True, session_id="s2")
    assert costs.session_total("s1") == pytest.approx(2 * PRICES[("sam-3.1", "image")])
    assert costs.session_total("s2") == pytest.approx(4 * PRICES[("sam-3.1", "image")])
    day = costs.day_total()
    reloaded = CostLog(root=tmp_path / "costs")  # relue au démarrage
    assert reloaded.day_total() == pytest.approx(day)  # SRV-R8.1 : persistance par jour
    assert reloaded.session_total("s1") == pytest.approx(costs.session_total("s1"))


def test_unknown_model_costs_zero_without_crashing(tmp_path):
    assert log(tmp_path).add("futur-modele-9.9", "image", 100, 1.0, True) == 0.0
