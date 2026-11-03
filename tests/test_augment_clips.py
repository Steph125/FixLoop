"""Copies transformées des extraits : test de robustesse (spec/08-evaluation, EVAL-R9, EVAL-T11).

Filtres ffmpeg déterministes, mêmes paramètres pour tout l'extrait ; étiquettes
copiées de l'original ; copies à part (`split = robust`). Vidéos synthétiques
écrites avec OpenCV dans tmp_path, jamais dans data/. Aucun appel réseau.
"""

import csv
import hashlib
import math
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import augment_clips as aug  # noqa: E402

FFMPEG = shutil.which("ffmpeg") is not None


def test_every_family_of_the_design_has_a_variant():
    families = {v["family"] for v in aug.VARIANTS.values()}
    assert families == {"distance", "cadrage", "lumière", "qualité", "caméra"}  # design 08 §9
    assert set(aug.DEFAULT_VARIANTS) == set(aug.VARIANTS)


def test_zoom_stays_inside_the_frame_and_follows_the_chainring():
    w, h = 848, 464
    vf = aug.filter_for("zoom13", w, h, center=(800, 440))  # plateau près du coin
    crop = vf.split(",")[0]
    cw, ch, x, y = (int(v) for v in crop.split("=")[1].split(":"))
    assert cw <= w / 1.3 + 2 and ch <= h / 1.3 + 2
    assert 0 <= x <= w - cw and 0 <= y <= h - ch  # jamais hors cadre
    assert x == w - cw and y == h - ch  # recadré vers le plateau, sans le couper
    assert vf.endswith(f"scale={w}:{h}")  # même taille que l'original


def test_rotation_crop_removes_black_corners():
    w, h = 848, 464
    s = aug.inscribed_scale(w, h, 4.0)
    a, t = w / h, math.radians(4.0)
    assert s <= 1 / (math.cos(t) + a * math.sin(t)) + 1e-9  # rectangle inscrit
    vf = aug.filter_for("rotate4", w, h)
    assert vf.startswith("rotate=") and f"scale={w}:{h}" in vf


def test_labels_and_rows_are_copied_from_the_original():
    rows = [{"clip": "L1", "t": 0, "state": "off", "done": 0},
            {"clip": "L1", "t": 1, "state": "on", "done": 1}]
    got = aug.copy_labels(rows, "L1-dark")
    assert [(r["clip"], r["t"], r["state"], r["done"]) for r in got] == [
        ("L1-dark", 0, "off", 0), ("L1-dark", 1, "on", 1)]  # EVAL-R9.2 : mêmes étiquettes
    clip = {"clip": "L1", "file": "data/eval/L1.MOV", "duration_s": "10.7", "lighting": "lampe",
            "angle": "face", "distance": "50cm", "scenario": "S1", "split": "test"}
    row = aug.robust_row(clip, "dark", "data/eval/aug/L1-dark.mp4")
    assert row["clip"] == "L1-dark" and row["split"] == "robust"  # EVAL-R9.4 : jamais `test`
    assert row["source"] == "L1" and row["transform"] == "dark"
    assert row["scenario"] == "S1" and row["lighting"] == "lampe"


def write_clip(path, n=30, fps=30, w=320, h=180):
    import cv2
    import numpy as np
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    assert writer.isOpened()
    for j in range(n):
        img = np.full((h, w, 3), 60, np.uint8)
        cv2.circle(img, (200, 110), 40, (200, 200, 200), -1)  # « plateau »
        cv2.circle(img, (60 + 4 * j, 50), 12, (80, 200, 80), -1)  # mouvement réel
        writer.write(img)
    writer.release()


def write_inputs(tmp_path):
    for name in ("c1", "c2"):
        write_clip(tmp_path / f"{name}.mp4")
    clips = tmp_path / "clips.csv"
    with clips.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["clip", "file", "duration_s", "lighting", "angle", "distance",
                    "scenario", "split"])
        w.writerow(["c1", str(tmp_path / "c1.mp4"), "1.0", "lampe", "face", "50cm", "S1", "test"])
        w.writerow(["c2", str(tmp_path / "c2.mp4"), "1.0", "soir", "plongee", "30cm", "S6", "test"])
        w.writerow(["k1", str(tmp_path / "c1.mp4"), "1.0", "soir", "face", "50cm", "S1", "calib"])
    labels = tmp_path / "labels.csv"
    with labels.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["clip", "t", "state", "done"])
        for clip in ("c1", "c2", "k1"):
            w.writerow([clip, "0", "off" if clip == "c1" else "on", "0"])
    return clips, labels


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg absent du PATH")
def test_copies_keep_duration_frames_size_and_labels(tmp_path):
    import cv2
    clips, labels = write_inputs(tmp_path)
    videos, out = tmp_path / "aug", tmp_path / "robust"
    info = aug.main(["--clips", str(clips), "--labels", str(labels),
                     "--out-video", str(videos), "--out", str(out)])
    assert info["copies"] == 2 * len(aug.VARIANTS)  # `test` seulement, `calib` exclu
    for name in ("c1", "c2"):
        for variant in aug.VARIANTS:
            copy = videos / f"{name}-{variant}.mp4"
            cap = cv2.VideoCapture(str(copy))
            assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) == 30  # même chronologie
            assert round(cap.get(cv2.CAP_PROP_FPS)) == 30
            assert (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))) == (320, 180)
            cap.release()
    rows = list(csv.DictReader((out / "clips.csv").open(encoding="utf-8")))
    assert {r["split"] for r in rows} == {"robust"} and len(rows) == 2 * len(aug.VARIANTS)
    assert not any(r["source"] == "k1" for r in rows)
    lab = list(csv.DictReader((out / "labels.csv").open(encoding="utf-8")))
    assert {(r["clip"], r["state"]) for r in lab if r["clip"].startswith("c1-")} == {
        (f"c1-{v}", "off") for v in aug.VARIANTS}

    digest = hashlib.sha256((videos / "c1-blur_noise.mp4").read_bytes()).hexdigest()
    aug.main(["--clips", str(clips), "--labels", str(labels), "--variants", "blur_noise",
              "--out-video", str(videos), "--out", str(tmp_path / "robust2")])
    assert hashlib.sha256((videos / "c1-blur_noise.mp4").read_bytes()).hexdigest() == digest


def test_failed_ffmpeg_raises_with_stderr(tmp_path, monkeypatch):
    import subprocess

    def fails(cmd, **kw):  # faux ffmpeg : sort en code 1
        return subprocess.CompletedProcess(cmd, 1, b"", b"x\nInvalid argument\n")

    monkeypatch.setattr(aug.shutil, "which", lambda name: "ffmpeg")
    monkeypatch.setattr(aug.subprocess, "run", fails)
    with pytest.raises(RuntimeError, match="Invalid argument"):
        aug.transform(tmp_path / "in.mp4", tmp_path / "out.mp4", "dark", 320, 180)
