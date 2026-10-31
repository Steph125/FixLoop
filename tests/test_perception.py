"""Tests de la partie commune de perception (spec/02-perception, PERC-T3).

Aucun appel réseau : les records SAM sont construits en local (vrais
`SegmentationMask` encodés, métadonnées factices), sauf un test de relecture
gardé qui saute si `probe_out2/` est absent.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from meta_sam_parser import SegmentationMask
from meta_sam_parser._mask_codec import _encode_raster  # test only: fabrique des payloads valides

from fixloop import perception
from fixloop.perception import (
    CONF_THR,
    lines_for,
    mask_to_svg_path,
    masks_from_records,
    parse_raw,
    plan_chunks,
    shift_frames,
)


def make_rec(bits: np.ndarray, left: float, top: float, confidence: float | None,
             frame_index: int | None = 0, kind: str = "mask"):
    """Un record factice avec un vrai masque décodable (bit 0/1 -> raster plein cadre via le module)."""
    h, w = bits.shape
    payload = _encode_raster(bytes(int(v) for v in bits.reshape(-1)), w, h)
    mask = SegmentationMask(encoding="one_bit", payload=payload, width=w, height=h)
    frame = None if frame_index is None else SimpleNamespace(frame_index=frame_index)
    return SimpleNamespace(kind=kind, confidence=confidence, mask=mask,
                           bounds=SimpleNamespace(left=left, top=top),
                           frame=frame, object_id="obj")


def test_place_full_frame_offset_box():
    bits = np.ones((3, 4), dtype=bool)
    out = masks_from_records([make_rec(bits, 5, 2, 0.9)], 10, 12, 0.4, False)
    assert set(out) == {0}
    assert out[0].mask.shape == (10, 12)
    assert out[0].mask[2:5, 5:9].all() and out[0].mask.sum() == 12
    assert out[0].box == (5, 2, 9, 5)
    assert out[0].confidence == pytest.approx(0.9)


def test_clip_at_frame_edge():
    bits = np.ones((4, 4), dtype=bool)
    out = masks_from_records([make_rec(bits, 10, 8, 0.7)], 10, 12, 0.4, False)
    assert out[0].mask.shape == (10, 12)
    assert out[0].mask[8:10, 10:12].all() and out[0].mask.sum() == 4
    assert out[0].box == (10, 8, 12, 10)


def test_largest_keeps_biggest():
    small = make_rec(np.ones((2, 2), dtype=bool), 0, 0, 0.95)
    big = make_rec(np.ones((3, 3), dtype=bool), 4, 4, 0.5)
    out = masks_from_records([small, big], 10, 10, 0.4, True)
    assert out[0].mask.sum() == 9 and out[0].n_objects == 1
    assert out[0].confidence == pytest.approx(0.5)


def test_union_merges_and_keeps_max_confidence():
    a = make_rec(np.ones((2, 2), dtype=bool), 0, 0, 0.6)
    b = make_rec(np.ones((2, 2), dtype=bool), 5, 5, 0.85)
    out = masks_from_records([a, b], 10, 10, 0.4, False)
    assert out[0].mask.sum() == 8 and out[0].n_objects == 2
    assert out[0].confidence == pytest.approx(0.85)


def test_confidence_filter_and_missing_confidence():
    low = make_rec(np.ones((2, 2), dtype=bool), 0, 0, 0.39)
    assert masks_from_records([low], 10, 10, 0.4, False) == {}
    edge = make_rec(np.ones((2, 2), dtype=bool), 0, 0, 0.4)
    assert set(masks_from_records([edge], 10, 10, 0.4, False)) == {0}
    assert CONF_THR == pytest.approx(0.4)
    noc = make_rec(np.ones((2, 2), dtype=bool), 0, 0, None)
    out = masks_from_records([noc], 10, 10, 0.4, False)
    assert out[0].confidence == pytest.approx(1.0)


def test_no_kept_object_means_absent():
    assert masks_from_records([], 10, 10, 0.4, False) == {}
    box = make_rec(np.ones((2, 2), dtype=bool), 0, 0, 0.9, kind="box")
    assert masks_from_records([box], 10, 10, 0.4, False) == {}


def test_video_records_grouped_by_frame():
    recs = [make_rec(np.ones((2, 2), dtype=bool), 0, 0, 0.9, fi) for fi in (0, 3)]
    out = masks_from_records(recs, 10, 10, 0.4, False)
    assert set(out) == {0, 3}


def test_image_records_without_frame_go_to_zero():
    rec = make_rec(np.ones((2, 2), dtype=bool), 1, 1, 0.9, None)
    out = masks_from_records([rec], 10, 10, 0.4, False)
    assert set(out) == {0} and out[0].mask[1, 1]


def test_plan_chunks():
    assert plan_chunks(570, 100) == [(0, 100), (100, 200), (200, 300),
                                    (300, 400), (400, 500), (500, 570)]
    assert plan_chunks(540, 100)[-1] == (400, 540)
    assert plan_chunks(30, 100) == [(0, 30)]
    assert plan_chunks(100, 100) == [(0, 100)]
    assert plan_chunks(140, 100) == [(0, 140)]
    assert plan_chunks(0, 100) == [(0, 0)]


def test_shift_frames():
    assert shift_frames("<0f>a\n<7f>b\n", 100) == "<100f>a\n<107f>b\n"
    assert shift_frames("", 5) == ""
    assert shift_frames("<3f>a", 2).endswith("\n")


def test_lines_for():
    text = "<0f>a\n<1f>b\n<2f>c\n"
    assert lines_for(text, {1}) == "<1f>b\n"
    assert lines_for(text, None) == text
    assert lines_for("", {0}) == ""


def test_cost_log_called_per_request():
    from fixloop.perception import LivePerception

    entries = []

    class FakeCosts:
        def add(self, **kw):
            entries.append(kw)
            return 0.0

    lp = LivePerception({"parts": {}}, client=object(), costs=FakeCosts())
    lp._cost("chain", 1.2, True, 1)
    lp._cost("chainring", 0.3, False, 3)
    assert [(e["model"], e["kind"], e["units"]) for e in entries] == [
        ("sam-3.1", "image", 1), ("sam-3.1", "image", 1)]  # PERC-R7.1
    assert [(e["part"], e["seconds"], e["ok"], e["attempts"]) for e in entries] == [
        ("chain", 1.2, True, 1), ("chainring", 0.3, False, 3)]
    LivePerception({"parts": {}}, client=object())._cost("chain", 1.0, True, 1)  # sans journal : rien


RAW_CHUNK = Path("probe_out2/raw_chain_00.txt")


def test_svg_path_is_small_and_offset():
    mask = np.zeros((30, 40), dtype=bool)
    mask[2:12, 5:15] = True  # 100 px² : au-dessus du seuil de 40 px²
    path = mask_to_svg_path(mask)
    assert path.startswith("M ") and path.endswith(" Z")  # PERC-R6.1
    assert len(path.encode()) < 4096  # PERC-R6.2
    xs = [int(token.split(",")[0]) for token in path[2:-2].split(" L ")]
    ys = [int(token.split(",")[1]) for token in path[2:-2].split(" L ")]
    assert (min(xs), min(ys), max(xs) + 1, max(ys) + 1) == (5, 2, 15, 12)  # PERC-R6.3 : plein cadre
    assert mask_to_svg_path(np.zeros((30, 40), dtype=bool)) == ""  # vide : chemin vide
    dot = np.zeros((30, 40), dtype=bool)
    dot[4, 4] = True
    assert mask_to_svg_path(dot) == ""  # moins de 40 px² : ignoré


def test_part_result_carries_svg_and_box():
    out = masks_from_records([make_rec(np.ones((10, 10), dtype=bool), 5, 2, 0.9)], 30, 40, 0.4, False)
    assert out[0].svg_path.startswith("M ") and len(out[0].svg_path.encode()) < 4096
    assert out[0].box == (5, 2, 15, 12)


@pytest.mark.skipif(not RAW_CHUNK.exists(), reason="probe_out2 absent")
def test_recorded_masks_svg_median_under_4k():
    import statistics

    from meta_sam_parser import decode_mask_to_raster, decode_mask_to_svg_path

    recs = []
    for name in ("probe_out2/raw_chain_00.txt", "probe_out2/raw_chainring_00.txt"):
        result = parse_raw(Path(name).read_text(encoding="utf-8"), video=True)
        recs += [r for r in result.records if r.kind == "mask"][:10]
    assert len(recs) == 20
    sizes, raw_sizes = [], []
    for rec in recs:
        mh, mw = rec.mask.height, rec.mask.width
        raster = np.frombuffer(decode_mask_to_raster(rec.mask), dtype=np.uint8)
        raster = raster.reshape(mh, mw).astype(bool)
        sizes.append(len(mask_to_svg_path(raster).encode()))
        raw_sizes.append(len(decode_mask_to_svg_path(rec.mask).encode()))
    assert max(sizes) < 4096  # PERC-R6.2 : médiane 303 o le 30 oct., contre 9344 o (voir PERC-D6)
    assert statistics.median(sizes) < statistics.median(raw_sizes)


@pytest.mark.skipif(not RAW_CHUNK.exists(), reason="probe_out2 absent")
def test_parse_raw_rereads_recorded_chunk():
    text = RAW_CHUNK.read_text(encoding="utf-8")
    result = parse_raw(text, video=True)
    masks = [r for r in result.records if r.kind == "mask"]
    assert masks, "le morceau enregistré doit contenir des masques"
    frames = {r.frame.frame_index for r in masks if r.frame is not None}
    one = next(iter(sorted(frames)))
    sub = masks_from_records(
        [r for r in result.records],
        464, 848, 0.4, False,
    )
    assert one in sub and sub[one].mask.shape == (464, 848)
    assert perception.__name__ == "fixloop.perception"
