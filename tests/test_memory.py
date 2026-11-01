"""Historique local du vélo (spec/04-memory-voice, MEM-T1). Aucun réseau, sans Wonder."""

from datetime import datetime, timedelta, timezone

import pytest

from fixloop.memory import WonderMemory


def mem(tmp_path):
    return WonderMemory(root=tmp_path / "bikes")


def report(**kw):
    base = {"procedure": "chain_off_chainring", "success": True, "duration_s": 142,
            "steps_validated": ["frame_view"], "anomalies": [], "model_calls": {"spark": 1}}
    base.update(kw)
    return base


def test_empty_history_returns_aucun_without_call(tmp_path):
    m = mem(tmp_path)
    assert m.load("velo-1") == "aucun"  # MEM-R1.1, R1.5 : pas d'appel Wonder
    assert m.calls == []


def test_save_then_plain_fallback(tmp_path):
    m = mem(tmp_path)
    m.save("velo-1", report())
    m.save("velo-1", report(success=False))
    text = m.load("velo-1")
    assert "chain_off_chainring" in text and "réussie" in text and "échouée" in text  # MEM-R1.6
    assert len(text.splitlines()) == 2  # les 5 dernières au plus


def test_repeated_counts_last_30_days(tmp_path):
    m = mem(tmp_path)
    old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    m.save("velo-1", report(date=old))
    m.save("velo-1", report())
    m.save("velo-1", report(procedure="autre_fiche"))
    assert m.repeated("velo-1", "chain_off_chainring") == 1  # MEM, design 1.2
    assert m.repeated("velo-9", "chain_off_chainring") == 0


def test_invalid_bike_id_refused(tmp_path):
    m = mem(tmp_path)
    for bad in ("Vélo!", "ab", "x" * 33, ""):
        with pytest.raises(ValueError):  # MEM-R3.2 : identifiant opaque
            m.load(bad)
        with pytest.raises(ValueError):
            m.save(bad, report())
        with pytest.raises(ValueError):
            m.repeated(bad, "chain_off_chainring")


def test_history_contains_no_image_audio_or_transcript(tmp_path):
    m = mem(tmp_path)
    m.save("velo-1", report(image=[1, 2], audio=b"xxx", transcript="coucou", nom="Léa"))
    raw = (tmp_path / "bikes" / "velo-1.json").read_text(encoding="utf-8")
    assert "image" not in raw and "audio" not in raw  # MEM-R3.1
    assert "transcript" not in raw and "Léa" not in raw
    assert "chain_off_chainring" in raw  # MEM-R2.1 : l'entrée est écrite
    assert list((tmp_path / "bikes").glob("*.tmp")) == []  # écriture atomique (MEM-R2.4)


def test_corrupt_history_renamed_and_empty(tmp_path):
    m = mem(tmp_path)
    path = tmp_path / "bikes" / "velo-1.json"
    path.parent.mkdir(parents=True)
    path.write_text("{ invalide", encoding="utf-8")
    assert m.load("velo-1") == "aucun"  # MEM-R1.1 : repart vide, sans lever
    assert not path.exists()
    renamed = list((tmp_path / "bikes").glob("velo-1.corrupt-*.json"))
    assert len(renamed) == 1 and "invalide" in renamed[0].read_text(encoding="utf-8")
    assert m.repeated("velo-1", "chain_off_chainring") == 0
    m.save("velo-1", report())  # reecriture possible apres renommage
    assert "chain_off_chainring" in m.load("velo-1")


def test_non_dict_history_renamed_and_empty(tmp_path):
    m = mem(tmp_path)
    path = tmp_path / "bikes" / "velo-1.json"
    path.parent.mkdir(parents=True)
    path.write_text("[1, 2]", encoding="utf-8")  # JSON valide mais inutilisable
    assert m.load("velo-1") == "aucun"
    assert len(list((tmp_path / "bikes").glob("velo-1.corrupt-*.json"))) == 1


def test_seed_history_creates_demo_entries(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path

    root = tmp_path / "bikes"
    r = subprocess.run(
        [sys.executable, "scripts/seed_history.py", "--bike", "demo-velo",
         "--root", str(root)],
        capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent)
    assert r.returncode == 0, r.stderr  # MEM-R4.1 : historique de demonstration
    data = json.loads((root / "demo-velo.json").read_text(encoding="utf-8"))
    assert len(data["entries"]) == 2
    assert all(e["procedure"] == "chain_off_chainring" and e.get("demo") is True
               for e in data["entries"])
    m = mem(tmp_path)
    assert m.repeated("demo-velo", "chain_off_chainring") == 2  # visible par MEM-T5


def wonder(tmp_path, answer, **kw):
    from fakes import FakeWonderClient
    from fixloop.memory import WonderMemory
    kw.setdefault("background", False)  # synchrone : déterministe sans API
    return WonderMemory(root=tmp_path / "bikes", client=FakeWonderClient(answer), **kw)


def test_load_with_client_returns_synthesis(tmp_path):
    m = wonder(tmp_path, " ".join(["mot"] * 100))  # 100 mots
    m.save("velo-1", report())
    text = m.load("velo-1")
    assert len(text.split()) <= 60  # MEM-R1.2 : synthèse de moins de 60 mots

    assert m.calls[-1]["kind"] == "synthesis"  # journal (MEM-T4)
    assert m.calls[-1]["ok"] is True


def test_load_sends_effort_and_timeout(tmp_path):
    m = wonder(tmp_path, "Synthèse courte.", effort="medium")
    m.save("velo-1", report())
    m.load("velo-1")
    sent = m.client.sent[0]
    assert sent["model"] == "muse-wonder-1.0"
    assert sent["reasoning"] == {"effort": "medium"}  # effort réglable (MEM-T4)
    assert sent["timeout"] == 20  # délai 20 s


def test_load_error_falls_back_to_plain_text(tmp_path):
    from fakes import FakeWonderClient
    from fixloop.memory import WonderMemory
    m = WonderMemory(root=tmp_path / "bikes", client=FakeWonderClient(ConnectionError("coupé")),
                     background=False)
    m.save("velo-1", report())
    assert "chain_off_chainring" in m.load("velo-1")  # MEM-R1.6 : repli texte brut
    assert m.calls[0]["error"] == "ConnectionError"


def test_save_adds_summary_below_30_words(tmp_path):
    m = wonder(tmp_path, "Chaîne remise après une tentative, test de rotation réussi.")
    m.save("velo-1", report())
    import json
    entry = json.loads((tmp_path / "bikes" / "velo-1.json").read_text(encoding="utf-8"))["entries"][0]
    assert "summary" in entry  # MEM-R2.2 : phrase de rapport
    assert len(entry["summary"].split()) <= 30
    assert m.calls[-1]["kind"] == "summary"


def test_save_background_writes_first_without_summary(tmp_path):
    import threading

    from fakes import FakeWonderClient
    from fixloop.memory import WonderMemory
    import json
    gate = threading.Event()
    m = WonderMemory(root=tmp_path / "bikes", client=FakeWonderClient("Résumé.", gate=gate),
                     background=True)
    m.save("velo-1", report())
    path = tmp_path / "bikes" / "velo-1.json"
    first = json.loads(path.read_text(encoding="utf-8"))["entries"][0]
    assert "summary" not in first  # MEM-D3 : l'entrée part sans résumé, closed aussitôt
    gate.set()  # Wonder répond…
    m.join()
    second = json.loads(path.read_text(encoding="utf-8"))["entries"][0]
    assert second["summary"] == "Résumé."  # …ajouté par une 2e écriture atomique


def test_load_background_returns_local_text_immediately(tmp_path):
    import threading

    from fakes import FakeWonderClient
    from fixloop.memory import WonderMemory
    sync = WonderMemory(root=tmp_path / "bikes",
                        client=FakeWonderClient("Résumé."),
                        background=False)
    sync.save("velo-1", report())
    gate = threading.Event()
    m = WonderMemory(root=tmp_path / "bikes",
                     client=FakeWonderClient("Synthèse de fond.", gate=gate),
                     background=True)
    text = m.load("velo-1")
    assert "chain_off_chainring" in text  # MEM-D3 : texte local tout de suite
    assert m.synthesis is None  # Wonder n'a pas encore répondu
    gate.set()
    m.join(timeout=10)
    assert m.synthesis == "Synthèse de fond."  # journalisée quand elle arrive
    assert m.calls[-1]["kind"] == "synthesis" and m.calls[-1]["ok"] is True


def test_wonder_calls_are_reported_to_costs(tmp_path):
    from fixloop.costs import CostLog
    from fakes import FakeWonderClient
    from fixloop.memory import WonderMemory
    log = CostLog(root=tmp_path / "costs")
    m = WonderMemory(root=tmp_path / "bikes",
                     client=FakeWonderClient("Synthèse.", {"input_tokens": 400, "output_tokens": 25}),
                     background=False, costs=log)
    m.save("velo-1", report())
    m.load("velo-1")
    assert log.by_model().get("muse-wonder-1.0", 0) > 0  # MEM-T4 : jetons journalisés
    assert log.entries[0]["call"] == "summary"
