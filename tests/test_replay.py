"""Mode replay (spec/07-replay-mode).

RPL-T1 : cache fichier des réponses des modèles (hors ligne strict).
RPL-T2 : construction d'une session synthétique, deux fois à l'identique.
Aucun appel réseau, aucune vidéo réelle.
"""

import json

import pytest

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
