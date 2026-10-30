"""Mode image de la perception (spec/02-perception, PERC-T4).

Aucun appel réseau : FakeSamClient rejoue des sorties SAM fabriquées en local
(vrais payloads encodés, lus par parse_responses_stream comme en direct).

Les tests async passent par arun() : si cette sandbox bloque la création de la
boucle asyncio (listen interdit), ils sont ignorés avec la raison ; la logique
a été exécutée par ailleurs sur une boucle sans socket (voir le journal).
"""

from __future__ import annotations

import asyncio
from unittest import mock

import cv2
import numpy as np
import pytest
from meta_sam_parser._mask_codec import _encode_raster  # test only: fabrique des payloads valides

from fakes import FakeSamClient
from fixloop import perception
from fixloop.perception import LivePerception, live_parts
from fixloop.procedures import load_all

PROCS = load_all()
PROC = PROCS["chain_off_chainring"]
H, W = 60, 80


def arun(coro):
    """asyncio.run, ou ignore si la sandbox interdit les sockets (pas de boucle)."""
    try:
        return asyncio.run(coro)
    except OSError as e:
        try:
            coro.close()  # évite « coroutine was never awaited » sur le chemin ignoré
        except RuntimeError:
            pass  # déjà démarrée : l'échec vient d'ailleurs, on le remonte tel quel
        if getattr(e, "winerror", None) == 10013 or e.errno in (1, 13):
            pytest.skip(f"pas de boucle asyncio dans cet environnement : {e}")
        raise


class FakeAuthError(Exception):
    def __init__(self):
        super().__init__("401 Unauthorized")
        self.status_code = 401


def sam_line(obj, left, top, bw, bh, conf):
    """Une vraie ligne de sortie SAM image : <0f>id<|box…|><|mask…|>."""
    bits = np.ones((bh, bw), dtype=bool)
    payload = _encode_raster(bytes(int(v) for v in bits.reshape(-1)), bw, bh)
    return (f"<0f>{obj}<|box;x1={left};y1={top};x2={left + bw};y2={top + bh};"
            f"w={W};h={H};c={conf}|>"
            f"<|mask;x=0;y=0;c={conf};data={bh},{bw},{payload}|>\n")


def jpeg_bytes(h=H, w=W):
    img = np.zeros((h, w, 3), np.uint8)
    img[:] = (60, 120, 200)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    assert ok
    return buf.tobytes()


def client_two_parts(**kw):
    texts = {"bicycle chain": sam_line(1, 5, 7, 12, 10, 0.9),
             "chainring": sam_line(2, 40, 30, 8, 8, 0.8)}
    return FakeSamClient(texts=texts, **kw)


def test_live_parts_skips_derailleur():
    assert live_parts(PROC) == ["chain", "chainring"]  # PERC-R1.9 : pas de 3e requête


def test_segment_image_requests_parts_in_parallel():
    async def main():
        client = client_two_parts()
        res = await LivePerception(PROC, client=client, retry_s=0).segment_image(
            jpeg_bytes(), 3, 1.5)
        return client, res

    client, res = arun(main())
    assert {c["input"][0]["content"][0]["text"] for c in client.created} == {"bicycle chain", "chainring"}
    assert client.max_concurrent == 2  # PERC-R1.1 : requêtes qui se chevauchent
    assert res.frame_index == 3 and res.t == 1.5  # PERC-R2.3
    assert res.error is None
    assert res.parts["chain"].mask.shape == (H, W)  # PERC-R1.3 : plein cadre
    assert res.parts["chainring"].box == (40, 30, 48, 38)
    assert res.parts["chain"].confidence == pytest.approx(0.9)


def test_request_uses_sam_image_contract():
    async def main():
        client = client_two_parts()
        await LivePerception(PROC, client=client, retry_s=0).segment_image(jpeg_bytes(), 0, 0.0)
        return client

    client = arun(main())
    kw = client.created[0]
    assert kw["model"] == "sam-3.1"  # PERC-R1.1
    assert kw["metadata"] == {"include_confidence": "true", "mask_encoding": "one_bit"}  # R1.2
    assert kw["stream"] is True
    kinds = [p["type"] for p in kw["input"][0]["content"]]
    assert kinds == ["input_text", "input_image"]


def test_timing_reported():
    async def main():
        client = client_two_parts()
        return await LivePerception(PROC, client=client, retry_s=0).segment_image(
            jpeg_bytes(), 0, 0.0)

    res = arun(main())
    assert res.timing["total_s"] >= 0  # PERC-R1.8
    assert res.timing["first_byte_s"] is not None
    assert res.timing["first_byte_s"] <= res.timing["total_s"]
    assert res.timing["attempts"] == {"chain": 1, "chainring": 1}


def test_retry_after_connection_error_then_success():
    from openai import APIConnectionError

    async def main():
        failures = {"bicycle chain": [APIConnectionError(message="coupé", request=None)]}
        client = client_two_parts(failures=failures)
        res = await LivePerception(PROC, client=client, retry_s=0).segment_image(
            jpeg_bytes(), 0, 0.0)
        return client, res

    client, res = arun(main())
    assert res.error is None and res.parts["chain"].mask is not None  # PERC-R4.1
    assert res.timing["attempts"]["chain"] == 2
    assert all(s.closed for s in client.streams)  # PERC-R4.5 : flux toujours fermé


def test_backoff_uses_5s_per_attempt():
    from openai import APIConnectionError

    async def main():
        failures = {"bicycle chain": [APIConnectionError(message="x", request=None)] * 2}
        client = client_two_parts(failures=failures)
        with mock.patch("asyncio.sleep", new_callable=mock.AsyncMock) as asleep:
            res = await LivePerception(PROC, client=client).segment_image(jpeg_bytes(), 0, 0.0)
        return asleep, res

    asleep, res = arun(main())
    backoff = [c.args[0] for c in asleep.call_args_list if c.args[0] > 0]
    assert backoff == [5.0, 10.0]  # PERC-R4.2
    assert res.timing["attempts"]["chain"] == 3 and res.error is None


def test_no_retry_on_auth_error():
    async def main():
        client = client_two_parts(failures={"bicycle chain": [FakeAuthError()]})
        res = await LivePerception(PROC, client=client, retry_s=0).segment_image(
            jpeg_bytes(), 0, 0.0)
        return client, res

    client, res = arun(main())
    assert res.timing["attempts"]["chain"] == 1  # PERC-R4.3 : pas de relance hors réseau
    assert res.parts["chain"].mask is None  # PERC-R4.4 : pièce absente, session continue
    assert "401" in (res.error or "") and "chain" in (res.error or "")
    assert res.parts["chainring"].mask is not None
    assert all(s.closed for s in client.streams)


def test_error_after_three_failed_attempts():
    from openai import APIConnectionError

    async def main():
        failures = {"bicycle chain": [APIConnectionError(message="x", request=None)] * 5,
                    "chainring": [APIConnectionError(message="x", request=None)] * 5}
        client = client_two_parts(failures=failures)
        return await LivePerception(PROC, client=client, retry_s=0).segment_image(
            jpeg_bytes(), 0, 0.0)

    res = arun(main())
    assert res.timing["attempts"] == {"chain": 3, "chainring": 3}
    assert res.error is not None  # PERC-R4.4 : résultat marqué error
    assert res.parts["chain"].mask is None and res.parts["chainring"].mask is None


def test_try_submit_limits_in_flight():
    async def main():
        gate = asyncio.Event()
        client = client_two_parts(gate=gate)
        perc = LivePerception(PROC, client=client, retry_s=0)
        tasks = [perc.try_submit(jpeg_bytes(), i, float(i)) for i in range(3)]
        assert all(t is not None for t in tasks)
        assert perc.in_flight == 3
        assert perc.try_submit(jpeg_bytes(), 99, 99.0) is None  # PERC-R2.2 : 4e refusée
        assert perc.dropped == 1
        gate.set()
        results = await asyncio.gather(*tasks)
        return perc, results

    perc, results = arun(main())
    assert perc.in_flight == 0 and all(r.error is None for r in results)


def test_to_frame_masks_skips_absent_parts():
    async def main():
        client = client_two_parts(failures={"bicycle chain": [FakeAuthError()]})
        return await LivePerception(PROC, client=client, retry_s=0).segment_image(
            jpeg_bytes(), 7, 2.0)

    res = arun(main())
    fm = res.to_frame_masks()
    assert fm.frame_index == 7 and fm.t == 2.0
    assert set(fm.masks) == {"chainring"}  # PERC-R1.6 : pas de masque vide
    assert fm.masks["chainring"].shape == (H, W)
