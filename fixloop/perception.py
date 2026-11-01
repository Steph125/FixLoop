"""Perception SAM 3.1 : partie commune (spec/02-perception, PERC-T3).

Regroupe la logique sans réseau partagée par le mode image et le mode vidéo :
placement des masques plein cadre, sélection largest/union, filtre de confiance,
relecture des sorties brutes, découpage en morceaux. Les sondes `probe/` restent
inchangées (preuves datées) ; ce module en reprend le comportement mesuré.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import re
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np
from meta_sam_parser import (
    CompletedOutcome,
    ResponsesStreamError,
    ResponsesStreamRefusalError,
    decode_mask_to_raster,
    image_segmentation_format,
    parse_responses_stream,
    video_segmentation_format,
)
from openai import APIConnectionError

from .models import FrameMasks


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


CONF_THR = _env_float("FIXLOOP_SAM_CONF", 0.4)
LIVE_WIDTH = _env_int("FIXLOOP_SAM_WIDTH", 848)
MAX_IN_FLIGHT = _env_int("FIXLOOP_SAM_INFLIGHT", 3)
CHUNK_SECONDS = _env_float("FIXLOOP_SAM_CHUNK_S", 10.0)
VIDEO_FPS = 10.0
SAM_MODEL = "sam-3.1"
BASE_URL = "https://api.meta.ai/v1"
IMAGE_ATTEMPTS = 3           # 1 essai + 2 relances (PERC-R4.1)
IMAGE_RETRY_S = 5.0          # attente avant relance : 5 s x tentative (PERC-R4.2)

RETRYABLE = (APIConnectionError, ResponsesStreamError, ConnectionError, TimeoutError)


@dataclass
class PartResult:
    """Masque d'une pièce sur une image (coordonnées plein cadre)."""

    mask: np.ndarray | None
    confidence: float = 0.0
    box: tuple[int, int, int, int] | None = None  # x0, y0, x1, y1
    svg_path: str | None = None  # rempli par PERC-T6
    n_objects: int = 0


@dataclass
class ImageResult:
    """Résultat du mode image pour une image."""

    frame_index: int
    t: float
    parts: dict[str, PartResult] = field(default_factory=dict)
    timing: dict = field(default_factory=dict)
    error: str | None = None
    w: int = 0
    h: int = 0

    def to_frame_masks(self) -> FrameMasks:
        """Assemble un FrameMasks ; les pièces absentes (masque None) sont omises (PERC-R1.6)."""
        kept = {p: pr for p, pr in self.parts.items() if pr.mask is not None}
        return FrameMasks(frame_index=self.frame_index, t=self.t,
                          masks={p: pr.mask for p, pr in kept.items()},
                          confidence={p: pr.confidence for p, pr in kept.items()})


def live_parts(procedure: dict) -> list[str]:
    """Pièces citées par une règle (succès, anomalie, must_hold), dans l'ordre de la fiche.

    Seules ces pièces sont segmentées en direct (PERC-R1.9) : pour
    `chain_off_chainring`, chaîne et plateau, pas le dérailleur.
    """
    cited: set[str] = set()
    for step in procedure.get("steps", []):
        for rule in step.get("success", []) + step.get("anomaly", []):
            for key in ("part", "a", "b"):
                if key in rule:
                    cited.add(rule[key])
    for rule in procedure.get("dynamic_test", {}).get("must_hold", []):
        for key in ("part", "a", "b"):
            if key in rule:
                cited.add(rule[key])
    return [p for p in procedure.get("parts", {}) if p in cited]


def _error_name(part: str, exc: BaseException) -> str:
    """`"<pièce>: <TypeErreur> <code>"` ; le code (401, 429…) quand il existe (PERC-R4.3)."""
    code = getattr(exc, "status_code", None)
    base = f"{part}: {type(exc).__name__}"
    return f"{base} {code}" if isinstance(code, int) else base


class LivePerception:
    """Segmentation en direct, une requête SAM par pièce, en parallèle (PERC-R1, R2, R4)."""

    def __init__(self, procedure: dict, client: Any | None = None, costs: Any | None = None,
                 retry_s: float = IMAGE_RETRY_S, max_in_flight: int = MAX_IN_FLIGHT):
        self.procedure = procedure
        if client is None:  # jamais dans les tests : la clé ne quitte pas le serveur
            from openai import AsyncOpenAI
            client = AsyncOpenAI(base_url=BASE_URL, api_key=os.environ["MODEL_API_KEY"], timeout=60)
        self.client, self.costs = client, costs
        self.retry_s, self.max_in_flight = retry_s, max_in_flight
        self.in_flight = 0
        self.dropped = 0

    def try_submit(self, jpeg: bytes, frame_index: int, t: float) -> Any | None:
        """Soumet une image sans attendre ; None si déjà 3 en cours (abandonnée, PERC-R2.2)."""
        if self.in_flight >= self.max_in_flight:
            self.dropped += 1
            return None
        self.in_flight += 1
        task = asyncio.get_running_loop().create_task(self._run(jpeg, frame_index, t))
        task.add_done_callback(self._task_done)
        return task

    async def _run(self, jpeg: bytes, frame_index: int, t: float) -> ImageResult:
        try:
            return await self.segment_image(jpeg, frame_index, t)
        finally:
            self.in_flight -= 1

    @staticmethod
    def _task_done(task: Any) -> None:
        try:
            task.exception()
        except (asyncio.CancelledError, Exception):
            pass  # l'erreur est déjà dans ImageResult.error ; ici on évite l'avertissement

    async def segment_image(self, jpeg: bytes, frame_index: int, t: float) -> ImageResult:
        """Segmente une image pour les pièces de live_parts (PERC-R1.1, R1.8, R1.9)."""
        parts = live_parts(self.procedure)
        img = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return ImageResult(frame_index, t, {}, {"total_s": 0.0, "attempts": {}}, "image: illisible")
        h, w = img.shape[:2]
        if w > LIVE_WIDTH:  # réduction seulement, jamais d'agrandissement
            img = cv2.resize(img, (LIVE_WIDTH, int(h * LIVE_WIDTH / w)), interpolation=cv2.INTER_AREA)
            ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ok:
                jpeg = buf.tobytes()
            h, w = img.shape[:2]
        data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
        t0 = time.monotonic()
        per = await asyncio.gather(*(self._segment_part(p, data_url, h, w) for p in parts))
        total = time.monotonic() - t0
        out: dict[str, PartResult] = {}
        attempts: dict[str, int] = {}
        errors: list[str] = []
        firsts: list[float] = []
        for part, (pr, n, first, err) in zip(parts, per):
            out[part] = pr
            attempts[part] = n
            if first is not None:
                firsts.append(first)
            if err is not None:
                errors.append(err)
        timing = {"total_s": round(total, 3),
                  "first_byte_s": round(min(firsts), 3) if firsts else None,
                  "attempts": attempts}
        return ImageResult(frame_index, t, out, timing,
                           "; ".join(errors) if errors else None, w, h)

    async def _segment_part(self, part: str, data_url: str, h: int, w: int
                            ) -> tuple[PartResult, int, float | None, str | None]:
        """Une pièce, avec relances réseau ; rend (résultat, tentatives, premier octet, erreur)."""
        prompt = self.procedure["parts"][part]
        largest = self.procedure.get("select", {}).get(part) == "largest"
        attempts = 0
        t0 = time.monotonic()
        while True:
            attempts += 1
            try:
                stream = await self.client.responses.create(
                    model=SAM_MODEL,
                    input=[{"type": "message", "role": "user", "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": data_url},
                    ]}],
                    metadata={"include_confidence": "true", "mask_encoding": "one_bit"},
                    stream=True,
                )
                try:
                    marks: dict[str, float] = {}
                    result = await parse_responses_stream(
                        self._timed(stream, marks), image_segmentation_format()).final_result()
                finally:
                    await stream.close()  # PERC-R4.5, y compris après une erreur
            except ResponsesStreamRefusalError as e:  # réponse refusée : pièce absente, sans relance
                self._cost(part, time.monotonic() - t0, False, attempts)
                return PartResult(None), attempts, None, _error_name(part, e)
            except RETRYABLE as e:
                if attempts >= IMAGE_ATTEMPTS:
                    self._cost(part, time.monotonic() - t0, False, attempts)
                    return PartResult(None), attempts, None, _error_name(part, e)
                await asyncio.sleep(self.retry_s * attempts)  # PERC-R4.2 : 5 s, puis 10 s
                continue
            except Exception as e:  # 400, 401, 402, 429… : pas de relance (PERC-R4.3)
                self._cost(part, time.monotonic() - t0, False, attempts)
                return PartResult(None), attempts, None, _error_name(part, e)
            first = marks["first"] - t0 if "first" in marks else None
            found = masks_from_records(result.records, h, w, CONF_THR, largest)
            pr = found.get(0, found.get(sorted(found)[0])) if found else PartResult(None)
            self._cost(part, time.monotonic() - t0, True, attempts)
            return pr, attempts, first, None

    @staticmethod
    async def _timed(stream: Any, marks: dict[str, float]) -> Any:
        """Relaye les événements en notant l'arrivée du premier octet (PERC-R1.8)."""
        async for ev in stream:
            kind = ev.get("type") if isinstance(ev, dict) else getattr(ev, "type", "")
            if "first" not in marks and kind == "response.output_text.delta":
                marks["first"] = time.monotonic()
            yield ev

    def _cost(self, part: str, seconds: float, ok: bool, attempts: int) -> None:
        """Journalise la requête (PERC-R7, exploité par PERC-T7) ; n'interrompt jamais."""
        if self.costs is None:
            return
        try:
            self.costs.add(model=SAM_MODEL, kind="image", units=1, seconds=seconds,
                           ok=ok, part=part, attempts=attempts)
        except Exception:
            pass


def parse_raw(text: str, video: bool = True) -> Any:
    """Relit une sortie brute SAM enregistrée, sans appel API (PERC-R5.1)."""
    fmt = video_segmentation_format() if video else image_segmentation_format()
    parser = fmt.create_parser()
    list(parser.push(text))
    return parser.finish(CompletedOutcome()).result


def lines_for(text: str, frames: set[int] | None) -> str:
    """Ne garde que les lignes <Nf> des images voulues (PERC-R5.2)."""
    if frames is None:
        return text
    keep = []
    for line in text.splitlines(keepends=True):
        m = re.match(r"<(\d+)f>", line)
        if m and int(m.group(1)) in frames:
            keep.append(line)
    return "".join(keep)


def masks_from_records(records: Any, h: int, w: int, conf_thr: float = CONF_THR,
                       largest: bool = False) -> dict[int, PartResult]:
    """Records SAM -> un PartResult par image (PERC-R1.3 à R1.6).

    Filtre `confidence >= conf_thr` (absente = 1,0), replace chaque masque de
    boîte à (left, top) en le tronquant au cadre, garde le plus gros objet si
    `largest` sinon fusionne (union). Les images sans objet retenu sont absentes
    du résultat. Les records sans image (mode image) vont à la clé 0.
    """
    per_frame: dict[int, list[tuple[np.ndarray, float]]] = {}
    for rec in records:
        if getattr(rec, "kind", None) != "mask":
            continue
        frame = getattr(rec, "frame", None)
        fi = frame.frame_index if frame is not None else 0
        conf = rec.confidence if rec.confidence is not None else 1.0
        if conf < conf_thr:
            continue
        mh, mw = rec.mask.height, rec.mask.width
        raster = np.frombuffer(decode_mask_to_raster(rec.mask), dtype=np.uint8)
        raster = raster.reshape(mh, mw).astype(bool)
        x0, y0 = int(rec.bounds.left), int(rec.bounds.top)
        sx0, sy0 = max(0, -x0), max(0, -y0)
        x0c, y0c = max(0, x0), max(0, y0)
        x1c, y1c = min(x0 + mw, w), min(y0 + mh, h)
        if x1c <= x0c or y1c <= y0c:
            continue
        full = np.zeros((h, w), dtype=bool)
        full[y0c:y1c, x0c:x1c] = raster[sy0:sy0 + y1c - y0c, sx0:sx0 + x1c - x0c]
        per_frame.setdefault(fi, []).append((full, conf))
    out: dict[int, PartResult] = {}
    for fi, objs in per_frame.items():
        if largest:
            m, conf = max(objs, key=lambda mc: int(mc[0].sum()))
            ys, xs = np.nonzero(m)
            box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
            out[fi] = PartResult(mask=m, confidence=conf, box=box,
                                 svg_path=mask_to_svg_path(m), n_objects=1)
        else:
            m = np.logical_or.reduce([o[0] for o in objs])
            ys, xs = np.nonzero(m)
            box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
            out[fi] = PartResult(mask=m, confidence=max(o[1] for o in objs),
                                 box=box, svg_path=mask_to_svg_path(m), n_objects=len(objs))
    return out


def mask_to_svg_path(mask: np.ndarray, tol: float = 1.5) -> str:
    """Contour d'un masque en chemin SVG (`"M x,y L x,y … Z"` par contour, entiers).

    Contours extérieurs simplifiés (`approxPolyDP`, tolérance 1,5 px), petits
    contours de moins de 40 px² ignorés : moins de 4 ko par pièce et par image
    (PERC-R6.1, R6.2). Les coordonnées sont celles du tableau donné : plein
    cadre si le masque est plein cadre.
    """
    cnts, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for cnt in cnts:
        if cv2.contourArea(cnt) < 40:
            continue
        pts = cv2.approxPolyDP(cnt, tol, True).reshape(-1, 2)
        if len(pts) < 3:
            continue
        out.append("M " + " L ".join(f"{int(x)},{int(y)}" for x, y in pts) + " Z")
    return " ".join(out)


FRAME_MARK = re.compile(r"<(\d+)f>")


def shift_frames(text: str, offset: int) -> str:
    """Décale les numéros d'image d'une sortie SAM (PERC-R3.4)."""
    if not text:
        return ""
    text = FRAME_MARK.sub(lambda m: f"<{int(m.group(1)) + offset}f>", text)
    return text if text.endswith("\n") else text + "\n"


VIDEO_RETRY_S = 10.0  # PERC-R4.2 : 10 s x tentative en mode vidéo
VIDEO_ATTEMPTS = 3  # 1 essai + 2 relances (PERC-R4.1)
VIDEO_MIN_IMAGES = 50  # facturation minimale par requête vidéo (PERC-R3.6, PERC-R7.2)


class VideoCancelled(RuntimeError):
    """L'appelant a refusé la facturation estimée (confirmation, PERC-R3.6)."""


def chunk_key(chunk_bytes: bytes, prompt: str) -> str:
    """Empreinte d'un morceau : contenu + prompt + modèle (PERC-R3.5)."""
    return hashlib.sha256(b"|".join([chunk_bytes, prompt.encode(), SAM_MODEL.encode()])).hexdigest()[:16]


def _prepare_video(src: Path, out_dir: Path, fps: float, width: int,
                   chunk_seconds: float) -> tuple[Path, int, int, int, list[tuple[Path, int, int]]]:
    """ffmpeg : fps img/s, largeur max, sans son, H.264, puis découpage (PERC-R3.1, R3.2)."""
    import shutil
    import subprocess

    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg introuvable : installe-le puis relance.")
    src, out_dir = Path(src), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    small = out_dir / "input_small.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
                    "-vf", f"fps={fps},scale='min({width},iw)':-2",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-pix_fmt", "yuv420p", "-an", str(small)], check=True)
    cap = cv2.VideoCapture(str(small))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    chunk_frames = int(round(chunk_seconds * fps)) if chunk_seconds > 0 else 0
    ranges = plan_chunks(n, max(chunk_frames, 50) if chunk_frames else 0)
    chunks = []
    for ci, (a, b) in enumerate(ranges):
        path = small if len(ranges) == 1 else out_dir / f"chunk_{ci:02d}.mp4"
        if len(ranges) > 1:
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(small),
                            "-vf", f"select=between(n\\,{a}\\,{b - 1}),setpts=N/({fps}*TB)",
                            "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast",
                            "-crf", "23", "-pix_fmt", "yuv420p", "-an", str(path)], check=True)
        chunks.append((path, a, b))
    return small, h, w, n, chunks


async def segment_video(video: str | Path, procedure: dict, out_dir: str | Path, *,
                        client: Any | None = None, costs: Any | None = None,
                        chunk_seconds: float = CHUNK_SECONDS, fps: float = VIDEO_FPS,
                        width: int = 960, confirm=None, prepare=None,
                        uploader=None, parts: list[str] | None = None) -> list[FrameMasks]:
    """Segmente une vidéo entière, morceau par morceau (PERC-R3, replay et évaluation).

    `prepare` (ffmpeg) et `uploader` (Files API) sont injectables pour les tests ;
    `confirm(billed_images) -> bool` valide la facturation estimée (PERC-R3.6).
    Par défaut, seules les pièces de `live_parts(procedure)` sont segmentées
    (PERC-R3.3) ; `parts=[...]` remplace cette liste (démonstration, benchmark).
    Rend un `FrameMasks` par image (temps = indice / fps).
    """
    if client is None:  # jamais dans les tests : la clé ne quitte pas le serveur
        from openai import AsyncOpenAI
        client = AsyncOpenAI(base_url=BASE_URL, api_key=os.environ["MODEL_API_KEY"], timeout=900)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    prepare = prepare or _prepare_video
    _, h, w, _, chunks = await asyncio.to_thread(prepare, Path(video), out, fps, width,
                                                 chunk_seconds)
    parts = list(parts) if parts is not None else live_parts(procedure)
    prompts = {p: procedure["parts"][p] for p in parts}
    raws: dict[str, dict[int, str]] = {p: {} for p in parts}
    jobs: list[tuple[str, int, int, int, str]] = []
    for p in parts:
        for ci, (path, a, b) in enumerate(chunks):
            key = chunk_key(Path(path).read_bytes(), prompts[p])
            f, kf = out / f"raw_{p}_{ci:02d}.txt", out / f"raw_{p}_{ci:02d}.key"
            if f.exists() and kf.exists() and kf.read_text(encoding="utf-8").strip() == key:
                raws[p][ci] = f.read_text(encoding="utf-8")  # PERC-R3.5 : cache réutilisé
            else:
                jobs.append((p, ci, a, b, key))
    if jobs:
        billed = sum(max(b - a, VIDEO_MIN_IMAGES) for _, _, a, b, _ in jobs)
        if confirm is not None and not confirm(billed):  # PERC-R3.6
            raise VideoCancelled(f"facturation estimée refusée : {billed} images")
        uploads: dict[int, str] = {}

        async def file_for(ci: int, path: Path) -> str:
            if ci not in uploads:
                if uploader is not None:
                    uploads[ci] = await uploader(path)
                else:
                    with open(path, "rb") as fh:
                        uploads[ci] = (await client.files.create(
                            file=fh, purpose="user_data")).id
            return uploads[ci]

        for p, ci, a, b, key in jobs:  # morceaux en série (coupures, PERC, design 4)
            raw = await _segment_video_part(client, costs, p, prompts[p],
                                            await file_for(ci, chunks[ci][0]), b - a)
            if raw is not None:
                (out / f"raw_{p}_{ci:02d}.txt").write_text(raw, encoding="utf-8")
                (out / f"raw_{p}_{ci:02d}.key").write_text(key)
                raws[p][ci] = raw
    merged: dict[str, str] = {}
    for p in parts:
        merged[p] = "".join(shift_frames(raws[p][ci], a) for ci, (_, a, _) in enumerate(chunks)
                            if ci in raws[p])
        (out / f"raw_{p}.txt").write_text(merged[p], encoding="utf-8")
    return assemble_frames(merged, h, w, fps, procedure.get("select", {}))


def assemble_frames(merged: dict[str, str], h: int, w: int, fps: float,
                    select: dict[str, str] | None = None) -> list[FrameMasks]:
    """Textes bruts recollés par pièce -> un FrameMasks par image (PERC-R3.4, synchrone)."""
    select = select or {}
    per_frame: dict[int, dict[str, PartResult]] = {}
    for p, text in merged.items():
        if not text:
            continue
        for fi, pr in masks_from_records(parse_raw(text).records, h, w, CONF_THR,
                                         select.get(p) == "largest").items():
            per_frame.setdefault(fi, {})[p] = pr
    frames = []
    for fi in sorted(per_frame):
        kept = {p: pr for p, pr in per_frame[fi].items() if pr.mask is not None}
        frames.append(FrameMasks(frame_index=fi, t=fi / fps,
                                 masks={p: pr.mask for p, pr in kept.items()},
                                 confidence={p: pr.confidence for p, pr in kept.items()}))
    return frames


async def _segment_video_part(client: Any, costs: Any, part: str, prompt: str,
                              file_id: str, n_images: int) -> str | None:
    """Une pièce d'un morceau, avec relances ; rend la sortie brute ou None (morceau en échec)."""
    attempts = 0
    t0 = time.monotonic()

    def vcost(ok: bool, attempts: int) -> None:
        if costs is None:
            return
        try:  # PERC-R7 : facturation vidéo max(images, 50) dans CostLog.add
            costs.add(model=SAM_MODEL, kind="video", units=n_images,
                      seconds=round(time.monotonic() - t0, 3), ok=ok,
                      part=part, attempts=attempts)
        except Exception:
            pass

    while True:
        attempts += 1
        try:
            stream = await client.responses.create(
                model=SAM_MODEL,
                input=[{"type": "message", "role": "user", "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_video", "file_id": file_id},
                ]}],
                metadata={"include_confidence": "true", "mask_encoding": "one_bit"},
                stream=True,
            )
            try:
                result = await parse_responses_stream(
                    stream, video_segmentation_format()).final_result()
            finally:
                await stream.close()  # PERC-R4.5, y compris après une erreur
        except ResponsesStreamRefusalError:  # morceau en échec, autres continués (design 4)
            vcost(False, attempts)
            return None
        except RETRYABLE:
            if attempts >= VIDEO_ATTEMPTS:
                vcost(False, attempts)
                return None
            await asyncio.sleep(VIDEO_RETRY_S * attempts)  # PERC-R4.2 : 10 s, puis 20 s
            continue
        except Exception as e:  # 401, 402, 429… : pas de relance, arrêt (design 6)
            vcost(False, attempts)
            if getattr(e, "status_code", None) in (401, 402, 429):
                raise
            return None
        vcost(True, attempts)
        return result.raw_output


def plan_chunks(n_frames: int, chunk_frames: int, min_frames: int = 50) -> list[tuple[int, int]]:
    """Découpe [0, n_frames) ; un dernier morceau < min_frames fusionné (PERC-R3.2)."""
    if chunk_frames <= 0 or chunk_frames >= n_frames:
        return [(0, n_frames)]
    starts = list(range(0, n_frames, chunk_frames))
    if len(starts) > 1 and n_frames - starts[-1] < min_frames:
        starts.pop()
    return [(a, starts[i + 1] if i + 1 < len(starts) else n_frames) for i, a in enumerate(starts)]
