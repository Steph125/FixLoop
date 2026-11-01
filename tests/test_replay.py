"""Mode replay (spec/07-replay-mode).

RPL-T1 : cache fichier des réponses des modèles (hors ligne strict).
RPL-T2 : construction d'une session synthétique, deux fois à l'identique.
Aucun appel réseau, aucune vidéo réelle.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "replay"))

from fixloop.cached_models import CachedAgent, CachedMemory, OfflineError

PROCS = {"chain_off_chainring": {"id": "chain_off_chainring", "title": "t", "steps": []}}
STEP = {"id": "engage_top_teeth", "instruction": "Pose la chaîne.",
        "success": [{"type": "contact_ratio_max", "a": "chain",
                     "b": "chainring", "threshold": 0.18}]}


def fake_agent():
    from fakes import FakeAgent
    return FakeAgent()


def test_cached_agent_records_then_replays_offline(tmp_path):
    import numpy as np

    from fixloop.models import Verdict
    cache = tmp_path / "a.models.json"
    img = np.zeros((40, 50, 3), np.uint8)
    online = CachedAgent(fake_agent(), cache)
    assert online.diagnose([img], PROCS, "aucun") == ("chain_off_chainring",
                                                     "La chaîne pend sous le plateau.")
    v = online.arbitrate(STEP, [img], [])
    assert isinstance(v, Verdict) and v.value == "0"
    assert online.explain(STEP, v, [img]) == ("Montre-moi le plateau de face.", "chain")
    assert online.help(STEP, [img]) == "Aide : vise les dents du haut."
    stored = json.loads(cache.read_text(encoding="utf-8"))
    assert len(stored) == 4  # RPL-R2.1 : une entrée par appel, jamais écrite à la main
    for entry in stored.values():
        assert set(entry) == {"kind", "response", "obtained", "model"}  # RPL-T1
        assert entry["obtained"]  # date d'obtention (RPL-R2.4)

    offline = CachedAgent(None, cache)  # mode hors ligne strict : sans modèle
    assert offline.diagnose([img], PROCS, "aucun") == ("chain_off_chainring",
                                                       "La chaîne pend sous le plateau.")
    v2 = offline.arbitrate(STEP, [img], [])
    assert (v2.value, v2.rule, v2.evidence, v2.message) == (v.value, v.rule, v.evidence, v.message)
    assert offline.explain(STEP, v2, [img]) == ("Montre-moi le plateau de face.", "chain")
    assert offline.help(STEP, [img]) == "Aide : vise les dents du haut."


def test_cached_agent_offline_missing_key_raises(tmp_path):
    import numpy as np

    cache = tmp_path / "vide.models.json"
    cache.write_text("{}", encoding="utf-8")
    offline = CachedAgent(None, cache)
    with pytest.raises(OfflineError):  # RPL-R2.4 : jamais de réponse inventée
        offline.diagnose([np.zeros((4, 4, 3), np.uint8)], PROCS, "aucun")


def test_cached_memory_offline_replays_recorded_text(tmp_path):
    from fakes import FakeWonderClient
    from fixloop.memory import WonderMemory
    root = tmp_path / "bikes"
    inner = WonderMemory(root=root, client=FakeWonderClient("Synthèse enregistrée."),
                         background=False)
    mem = CachedMemory(inner, tmp_path / "m.models.json", root=root)
    mem.save("velo-1", {"procedure": "chain_off_chainring", "success": True})
    assert mem.load("velo-1") == "Synthèse enregistrée."  # synthèse Wonder, pas le repli local

    rebuilt = CachedMemory(None, tmp_path / "m.models.json", root=root)
    assert rebuilt.load("velo-1") == mem.load("velo-1")  # RPL-R2.3 : identique hors ligne
    assert rebuilt.repeated("velo-1", "chain_off_chainring") == 1


def synthetic_session(**kw):
    base = {"name": "syn-A", "title": "Erreur corrigée (synthétique)",
            "filmed": "2026-11-01", "source": "synthetic", "debounce_frames": 4,
            "bike_id": "demo-velo", "demo_history": False,
            "segments": [["off", 4], ["on", 6]], "user_done": [3.5, 5.0]}
    base.update(kw)
    return base


def test_synthetic_build_is_deterministic(tmp_path):
    from build_replay import build
    out1, out2 = tmp_path / "b1", tmp_path / "b2"
    build(synthetic_session(), out1, bikes_root=tmp_path / "bikes1")
    build(synthetic_session(), out2, bikes_root=tmp_path / "bikes2")
    for name in ("events.json", "overlays.json"):
        a = (out1 / "syn-A" / name).read_bytes()
        b = (out2 / "syn-A" / name).read_bytes()
        assert a == b and len(a) > 100  # RPL-R2.3 : identique octet par octet
    import json
    events = json.loads((out1 / "syn-A" / "events.json").read_text(encoding="utf-8"))
    assert [e["event"] for e in events].count("validated") == 3
    assert (out1 / "syn-A" / "video.mp4").exists()
    assert (out1 / "index.json").exists()  # sélecteur de session du lecteur


def test_synthetic_overlays_under_2mb_for_60_seconds(tmp_path):
    from build_replay import build
    out = tmp_path / "b60"
    build(synthetic_session(name="syn-60", segments=[["off", 30], ["on", 30]],
                            user_done=[3.5, 5.0, 40.0]),
          out, bikes_root=tmp_path / "bikes60")
    size = (out / "syn-60" / "overlays.json").stat().st_size
    assert size < 2 * 1024 * 1024  # RPL-R7.1 : 5 images/s


def test_state_at_replays_step_say_and_highlight():
    from build_replay import state_at
    events = [{"t": 0.0, "event": "step", "step": "frame_view"},
              {"t": 1.0, "event": "say", "text": "Place le téléphone."},
              {"t": 2.0, "event": "highlight", "parts": ["chain"], "color": "red"},
              {"t": 3.0, "event": "step", "step": "engage_top_teeth"}]
    assert state_at(events, 0.5) == {"step": "frame_view", "say": None,
                                     "highlight": {}}
    assert state_at(events, 2.5) == {"step": "frame_view",
                                     "say": "Place le téléphone.",
                                     "highlight": {"chain": "red"}}
    assert state_at(events, 3.0)["step"] == "engage_top_teeth"


def test_nearest_overlay_picks_closest_frame():
    from build_replay import nearest_overlay
    overlays = [{"t": 0.0}, {"t": 0.2}, {"t": 0.4}]
    assert nearest_overlay(overlays, 0.29) == {"t": 0.2}
    assert nearest_overlay(overlays, 9.0) == {"t": 0.4}


def test_video_source_needs_real_models():
    from build_replay import build
    import pytest
    with pytest.raises(RuntimeError, match="EVAL-T7"):
        build(synthetic_session(source="video", video="data/velo3.mp4"),
              "build", bikes_root="bikes")


def test_cached_memory_offline_refuses_changed_history(tmp_path):
    from fixloop.memory import WonderMemory
    root = tmp_path / "bikes"
    mem = CachedMemory(WonderMemory(root=root), tmp_path / "m.models.json", root=root)
    mem.save("velo-1", {"procedure": "chain_off_chainring", "success": True})
    mem.load("velo-1")
    mem.save("velo-1", {"procedure": "chain_off_chainring", "success": False})
    rebuilt = CachedMemory(None, tmp_path / "m.models.json", root=root)
    with pytest.raises(OfflineError):  # historique modifié depuis l'enregistrement
        rebuilt.load("velo-1")
