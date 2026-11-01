"""Chemin réel du replay (spec/07-replay-mode, RPL-T2).

Sources `video` et `recording` avec de FAUX clients (SAM, Spark) et des vidéos
synthétiques écrites avec OpenCV dans tmp_path (jamais dans data/).
Seule l'EXÉCUTION avec les vraies vidéos et la vraie clé est pour l'auteur
(RPL-T4, EVAL-T7). Aucun appel réseau ici.
"""

import json
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "replay"))

from build_replay import build  # noqa: E402
from fakes import FakeAgent, FakeSamClient  # noqa: E402


def write_mp4(path, n_frames, fps=10, w=400, h=400):
    """Vidéo synthétique écrite avec OpenCV (jamais dans data/)."""
    import cv2
    import numpy as np
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"),
                             fps, (w, h))
    assert writer.isOpened()
    for i in range(n_frames):
        img = np.full((h, w, 3), 40, np.uint8)
        cv2.circle(img, (w // 2, h // 2), 60, (220, 220, 220), -1)
        cv2.circle(img, (w // 2 + i % 5, h // 2), 20, (80, 200, 80), -1)
        writer.write(img)
    writer.release()


def raw_mask_line(obj, fi, mask, conf=0.9, video=True):
    """Sortie SAM brute valide depuis un masque (même format que le direct).

    Une ligne par objet avec sa boîte ajustée, comme le vrai SAM (le parser
    ignore les boîtes plein cadre).
    """
    import cv2
    import numpy as np
    from meta_sam_parser._mask_codec import _encode_raster
    h, w = np.asarray(mask, dtype=bool).shape
    tag = f"<{fi}f>" if video else "<0f>"
    cnts, _ = cv2.findContours(np.asarray(mask, dtype=np.uint8),
                               cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    lines = []
    for cnt in cnts:
        x, y, bw, bh = cv2.boundingRect(cnt)
        sub = np.asarray(mask, dtype=bool)[y:y + bh, x:x + bw]
        payload = _encode_raster(bytes(int(v) for v in sub.reshape(-1)), bw, bh)
        lines.append(
            f"{tag}{obj}<|box;x1={x};y1={y};x2={x + bw};y2={y + bh};"
            f"w={w};h={h};c={conf}|>"
            f"<|mask;x=0;y=0;c={conf};data={bh},{bw},{payload}|>\n")
    return "".join(lines)


def sim_raws(n_frames, n_off, video=True):
    """Textes bruts SAM pour n images : off puis on (contacts réels)."""
    from fixloop.sim import frame as sim_frame
    chain, ring = [], []
    for fi in range(n_frames):
        fm = sim_frame("off" if fi < n_off else "on", fi, fi / 10.0)
        chain.append(raw_mask_line(1, fi, fm.masks["chain"], video=video))
        ring.append(raw_mask_line(2, fi, fm.masks["chainring"], video=video))
    return {"chain": "".join(chain), "chainring": "".join(ring)}


def video_session(video_path, **kw):
    base = {"name": "vid-A", "title": "Session vidéo", "filmed": "2026-10-31",
            "source": "video", "video": str(video_path), "debounce_frames": 4,
            "bike_id": "demo-velo", "demo_history": False, "procedure": "chain_off_chainring",
            "diagnose_at": [0.1, 0.5, 1.0], "user_done": [1.2, 1.6]}
    base.update(kw)
    return base


def test_video_build_with_fake_sam_and_spark_is_deterministic(tmp_path):
    video = tmp_path / "velo.mp4"
    write_mp4(video, 20)
    raws = sim_raws(20, 10)
    sam = FakeSamClient(texts={"bicycle chain": raws["chain"],
                               "chainring": raws["chainring"]})
    assert sam.texts["bicycle chain"].startswith("<0f>")  # sorties brutes du faux client

    def fetch(video_path, procedure, sam_dir):
        sam_dir = Path(sam_dir)
        sam_dir.mkdir(parents=True, exist_ok=True)
        mapping = {"chain": "bicycle chain", "chainring": "chainring"}
        out = {}
        for part, prompt in mapping.items():
            text = sam.texts[prompt]  # le faux client SAM fournit les sorties brutes
            (sam_dir / f"raw_{part}.txt").write_text(text, encoding="utf-8")
            out[part] = text
        return out

    out1, out2, cache = tmp_path / "b1", tmp_path / "b2", tmp_path / "cache"
    build(video_session(video), out1, bikes_root=tmp_path / "bikes1",
          cache_dir=cache, agent="fixloop", spark_inner=FakeAgent(), raws_fn=fetch)
    build(video_session(video), out2, bikes_root=tmp_path / "bikes2",
          cache_dir=cache, agent="fixloop", spark_inner=FakeAgent(), raws_fn=fetch)
    for name in ("events.json", "overlays.json"):
        a = (out1 / "vid-A" / name).read_bytes()
        b = (out2 / "vid-A" / name).read_bytes()
        assert a == b and len(a) > 100  # RPL-R2.3 : identique octet par octet
    meta = json.loads((out1 / "vid-A" / "meta.json").read_text(encoding="utf-8"))
    assert meta["source"] == "video"  # RPL-T2 : vidéo 10 images/s, anti-rebond 4
    assert meta["filmed"] == "2026-10-31"
    assert "10 images/s" in meta["mode"] and "anti-rebond 4" in meta["mode"]
    assert (out1 / "vid-A" / "video.mp4").exists()
    events = json.loads((out1 / "vid-A" / "events.json").read_text(encoding="utf-8"))
    assert [e["event"] for e in events].count("validated") >= 1


def test_video_offline_replays_cache_without_calls(tmp_path):
    video = tmp_path / "velo.mp4"
    write_mp4(video, 20)
    texts = sim_raws(20, 10)
    calls = []

    def fetch(video_path, procedure, sam_dir):
        calls.append("fetch")
        sam_dir = Path(sam_dir)
        sam_dir.mkdir(parents=True, exist_ok=True)
        for part, text in texts.items():
            (sam_dir / f"raw_{part}.txt").write_text(text, encoding="utf-8")
        return dict(texts)

    out, cache = tmp_path / "b", tmp_path / "cache"
    build(video_session(video), out, bikes_root=tmp_path / "bikes",
          cache_dir=cache, agent="fixloop", spark_inner=FakeAgent(), raws_fn=fetch)
    assert len(calls) == 1
    before = (out / "vid-A" / "events.json").read_bytes()
    build(video_session(video), out, bikes_root=tmp_path / "bikes",
          cache_dir=cache, agent="fixloop", offline=True, raws_fn=fetch)
    assert len(calls) == 1  # --offline : aucun nouvel appel SAM
    after = (out / "vid-A" / "events.json").read_bytes()
    assert before == after  # RPL-R2.3 : rejoué à l'identique hors ligne


def test_video_offline_missing_spark_cache_raises(tmp_path):
    from pathlib import Path
    video = tmp_path / "velo.mp4"
    write_mp4(video, 20)
    texts = sim_raws(20, 10)
    sam_dir = tmp_path / "b" / "vid-A" / "sam"  # SAM en cache, Spark absent
    sam_dir.mkdir(parents=True)
    for part, text in texts.items():
        (sam_dir / f"raw_{part}.txt").write_text(text, encoding="utf-8")

    def fetch(video_path, procedure, sam_dir):
        raise AssertionError("aucun appel SAM hors ligne")

    from fixloop.cached_models import OfflineError
    with pytest.raises(OfflineError):  # RPL-R2.4 : jamais de réponse inventée
        build(video_session(video), tmp_path / "b", bikes_root=tmp_path / "bikes",
              cache_dir=tmp_path / "vide", agent="fixloop", offline=True,
              raws_fn=fetch)


def write_recording(path, n_frames=10):
    """Session en direct enregistrée : images 1/s + sorties SAM brutes."""
    import cv2
    import numpy as np
    path = Path(path)
    (path / "frames").mkdir(parents=True)
    for i in range(n_frames):
        img = np.full((400, 400, 3), 40, np.uint8)
        cv2.circle(img, (200, 200), 60, (220, 220, 220), -1)
        cv2.imwrite(str(path / "frames" / f"{i:04d}.jpg"), img)
    texts = sim_raws(n_frames, n_frames // 2, video=False)
    (path / "raw_chain.txt").write_text(texts["chain"], encoding="utf-8")
    (path / "raw_chainring.txt").write_text(texts["chainring"], encoding="utf-8")
    (path / "frames.json").write_text('{"w": 400, "h": 400, "fps": 1.0}',
                                      encoding="utf-8")


def test_recording_build_is_deterministic_and_offline(tmp_path):
    rec = tmp_path / "rec1"
    write_recording(rec)
    session = {"name": "rec-A", "title": "Direct enregistré", "filmed": "2026-10-31",
               "source": "recording", "recording": str(rec), "debounce_frames": 3,
               "bike_id": "demo-velo", "demo_history": True,
               "procedure": "chain_off_chainring", "user_done": [6.0, 8.0]}
    out1, out2, cache = tmp_path / "b1", tmp_path / "b2", tmp_path / "cache"
    build(dict(session), out1, bikes_root=tmp_path / "bikes1",
          cache_dir=cache, agent="fixloop", spark_inner=FakeAgent())
    build(dict(session), out2, bikes_root=tmp_path / "bikes2",
          cache_dir=cache, agent="fixloop", spark_inner=FakeAgent())
    for name in ("events.json", "overlays.json"):
        assert (out1 / "rec-A" / name).read_bytes() == (out2 / "rec-A" / name).read_bytes()
    meta = json.loads((out1 / "rec-A" / "meta.json").read_text(encoding="utf-8"))
    assert meta["source"] == "recording"
    assert "1 image/s" in meta["mode"] and "anti-rebond 3" in meta["mode"]
    before = (out1 / "rec-A" / "events.json").read_bytes()
    build(dict(session), out1, bikes_root=tmp_path / "bikes1",
          cache_dir=cache, agent="fixloop", offline=True)
    assert (out1 / "rec-A" / "events.json").read_bytes() == before
