"""Chemin réel du replay (spec/07-replay-mode, RPL-T2).

Sources `video` et `recording` avec de FAUX clients (SAM, Spark) et des vidéos
synthétiques écrites avec OpenCV dans tmp_path (jamais dans data/).
Seule l'EXÉCUTION avec les vraies vidéos et la vraie clé est pour l'auteur
(RPL-T4, EVAL-T7). Aucun appel réseau ici.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "replay"))

import build_replay  # noqa: E402
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


# --- RPL-D5 : vidéo publiée sans piste audio, jamais de copie OpenCV muette sur échec ffmpeg ---

def fake_fetch(texts):
    """`raws_fn` : sorties brutes SAM du faux client, écrites dans le cache."""
    def fetch(video_path, procedure, sam_dir):
        sam_dir = Path(sam_dir)
        sam_dir.mkdir(parents=True, exist_ok=True)
        for part, text in texts.items():
            (sam_dir / f"raw_{part}.txt").write_text(text, encoding="utf-8")
        return dict(texts)
    return fetch


def build_vid(video, out, tmp_path, **kw):
    return build(video_session(video), out, bikes_root=tmp_path / "bikes" / out.name,
                 cache_dir=tmp_path / "cache" / out.name, agent="fixloop",
                 spark_inner=FakeAgent(), raws_fn=fake_fetch(sim_raws(20, 10)), **kw)


def ffmpeg_ok(cmd, **kw):
    return subprocess.CompletedProcess(cmd, 0, b"", b"")


def test_encode_video_drops_audio_unless_keep_audio(tmp_path, monkeypatch):
    cmds = []
    monkeypatch.setattr(build_replay.shutil, "which", lambda name: "ffmpeg")
    monkeypatch.setattr(build_replay.subprocess, "run",
                        lambda cmd, **kw: cmds.append(cmd) or ffmpeg_ok(cmd))
    assert build_replay.encode_video(tmp_path / "in.mp4", tmp_path / "a.mp4") == "h264"
    build_replay.encode_video(tmp_path / "in.mp4", tmp_path / "b.mp4", keep_audio=True)
    assert "-an" in cmds[0]  # RPL-D5 : sans piste audio par défaut
    assert "-an" not in cmds[1]  # --keep-audio : décision explicite de l'auteur


def test_video_without_ffmpeg_marks_opencv_codec(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(build_replay.shutil, "which", lambda name: None)  # faux which
    video = tmp_path / "velo.mp4"
    write_mp4(video, 20)
    out = tmp_path / "b"
    build_vid(video, out, tmp_path)
    meta = json.loads((out / "vid-A" / "meta.json").read_text(encoding="utf-8"))
    assert meta["video_codec"] == "opencv-mp4v"  # copie permise, marquée (RPL-D5)
    assert (out / "vid-A" / "video.mp4").stat().st_size > 0
    assert "ffmpeg introuvable" in capsys.readouterr().err  # avertissement affiché

    rec = tmp_path / "rec1"
    write_recording(rec)
    build({"name": "rec-A", "title": "Direct", "filmed": "2026-10-31",
           "source": "recording", "recording": str(rec), "procedure": "chain_off_chainring",
           "user_done": [6.0, 8.0]}, out, bikes_root=tmp_path / "bikes-rec",
          cache_dir=tmp_path / "cache-rec", agent="fixloop", spark_inner=FakeAgent())
    meta = json.loads((out / "rec-A" / "meta.json").read_text(encoding="utf-8"))
    assert meta["video_codec"] == "opencv-mp4v"  # `recording` : même garde-fou
    assert sorted(p.name for p in (out / "rec-A").glob("*.mp4")) == ["video.mp4"]


def test_video_build_raises_when_ffmpeg_fails(tmp_path, monkeypatch):
    fake_ffmpeg = str(tmp_path / "ffmpeg.exe")
    calls = []

    def ffmpeg_fails(cmd, **kw):  # faux ffmpeg : sort en code 1
        calls.append(cmd)
        return subprocess.CompletedProcess(
            cmd, 1, b"", b"ffmpeg version x\nInput #0\nvelo.mp4: Invalid data found\n")

    monkeypatch.setattr(build_replay.shutil, "which", lambda name: fake_ffmpeg)
    monkeypatch.setattr(build_replay.subprocess, "run", ffmpeg_fails)
    video = tmp_path / "velo.mp4"
    write_mp4(video, 20)
    out = tmp_path / "b"
    with pytest.raises(RuntimeError, match="Invalid data found"):  # fin de stderr
        build_vid(video, out, tmp_path)
    assert calls and calls[0][0] == fake_ffmpeg
    assert not (out / "vid-A" / "video.mp4").exists()  # jamais de copie OpenCV
    assert not (out / "vid-A" / "meta.json").exists()


def audio_streams(path) -> int:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a",
                          "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return len(out.split())


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                    reason="ffmpeg ou ffprobe absent du PATH")
def test_built_video_has_no_audio_track(tmp_path):
    video = tmp_path / "velo_son.mp4"  # 20 images 400 x 400 + un son, jamais dans data/
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-f", "lavfi", "-i", "testsrc=size=400x400:rate=10:duration=2",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    str(video)], check=True)
    assert audio_streams(video) == 1
    muted, kept = tmp_path / "muet", tmp_path / "son"
    build_vid(video, muted, tmp_path)
    build_vid(video, kept, tmp_path, keep_audio=True)
    meta = json.loads((muted / "vid-A" / "meta.json").read_text(encoding="utf-8"))
    assert meta["video_codec"] == "h264"
    assert audio_streams(muted / "vid-A" / "video.mp4") == 0  # RPL-D5 : sans son
    assert audio_streams(kept / "vid-A" / "video.mp4") == 1  # --keep-audio
