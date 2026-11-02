"""Construction d'une session replay (spec/07-replay-mode, RPL-T2).

Usage : python replay/build_replay.py replay/sessions/syn-A.json --out replay/build
       [--bikes-root data/bikes] [--cache replay/cache] [--offline] [--agent rules|fixloop]
       [--sam-dir <dossier>] [--keep-audio] [--session-video ...]

Le rejeu exécute le même code que le direct (`Session`, `geometry`, `verifier`,
`fixloop/benchmark.py`) ; seules les réponses des modèles viennent d'un cache
(`CachedAgent`, `CachedMemory`, RPL-R2).

Sources :
- `synthetic` : scène `fixloop/sim.py`, sans vidéo ni API (tests, code seul) ;
- `video` : vidéo filmée par l'auteur (`segment_video`, cache `raw_*.txt`,
  mesures, `CachedAgent(SparkAgent)`, images clés recadrées, vidéo réencodée
  ffmpeg H.264 ≤ 960 px `+faststart` sans piste audio (RPL-D5), `meta.source = "video"`,
  « vidéo 10 images/s, anti-rebond 4 ») ;
- `recording` : session en direct enregistrée (`recording/` : images 1/s +
  sorties SAM brutes, `meta.source = "recording"`,
  « 1 image/s, anti-rebond 3 »).

« Sans vidéos ni API » : le chemin réel s'ÉCRIT et se TESTE ici avec de FAUX
clients (SAM, Spark) et des vidéos synthétiques écrites avec OpenCV ; seule
son EXÉCUTION avec les vraies vidéos et la vraie clé est pour l'auteur
(RPL-T4, EVAL-T7). Le transport réseau (`segment_video`, async) reste pour
l'auteur : les tests injectent `raws_fn` qui fournit les mêmes sorties brutes
SAM (payloads valides fabriqués avec `meta_sam_parser._mask_codec`), relues
par le vrai `parse_raw`/`assemble_frames` (décision RPL-D1 : même code).
"""

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fixloop.benchmark import CannedAgent, NoSparkAgent, classify_contact, drive_session  # noqa: E402
from fixloop.cached_models import CachedAgent, CachedMemory  # noqa: E402
from fixloop.memory import WonderMemory  # noqa: E402

FPS = 10.0  # mode vidéo (RPL-D3) : 10 images/s, anti-rebond 4
OVERLAY_EVERY = 2  # contours à 5 images/s (RPL-D4 : sous 2 Mo pour 60 s)
VIDEO_WIDTH = 960  # réencodage ffmpeg : ≤ 960 px (RPL-T2)
VIDEO_CODEC = "h264"  # `meta.video_codec` quand ffmpeg a réencodé
OPENCV_CODEC = "opencv-mp4v"  # copie sans ffmpeg : refusée par deploy_check.py (RPL-D5)
RECORDING_FPS = 1.0  # mode enregistrement (RPL-D3) : 1 image/s, anti-rebond 3


def state_at(events: list[dict], t: float) -> dict:
    """État affiché à l'instant `t` : rejeu des événements (design 07, section 4).

    Porté tel quel en JavaScript (`web/replay.js`) ; la référence Python est
    testée dans `tests/test_replay.py`.
    """
    out = {"step": None, "say": None, "highlight": {}}
    for e in events:
        if e.get("t", 0.0) > t + 1e-9:
            break
        if e.get("event") == "step":
            out["step"] = e.get("step")
        elif e.get("event") == "say":
            out["say"] = e.get("text")
        elif e.get("event") == "highlight":
            for part in e.get("parts", []):
                out["highlight"][part] = e.get("color", "blue")
    return out


def nearest_overlay(frames: list[dict], t: float) -> dict:
    """Image d'overlay la plus proche de `t` (recherche dichotomique côté lecteur)."""
    return min(frames, key=lambda f: (abs(f["t"] - t), f["t"]))


def model_for(event: dict):
    """Modèle Meta concerné par un événement, ou None (RPL-R4.3)."""
    kind = event.get("event")
    if kind in ("diagnose", "arbitrate"):
        return "muse-spark-1.3"
    if kind == "anomaly":
        return "muse-spark-1.3" if event.get("source") == "muse-spark" else "sam-3.1"
    if kind in ("validated", "step", "dynamic_start"):
        return "sam-3.1"  # décision géométrique sur mesures SAM
    return None


class TSOut:
    """Sortie qui horodate `say` / `highlight` avec le temps de la session."""

    def __init__(self) -> None:
        self.session = None
        self.events: list[dict] = []

    def _t(self) -> float:
        return round(self.session.t, 2) if self.session is not None else 0.0

    def say(self, text: str) -> None:
        self.events.append({"t": self._t(), "event": "say", "text": text})

    def highlight(self, parts, color: str) -> None:
        self.events.append({"t": self._t(), "event": "highlight",
                            "parts": list(parts), "color": color})

    def state(self, snapshot: dict) -> None:
        pass  # l'état est recalculé par `state_at`, jamais stocké


def render_frame(fm) -> object:
    """Image BGR synthétique depuis les masques (vidéo du replay, sans vraie caméra)."""
    import numpy as np
    h, w = next(iter(fm.masks.values())).shape
    img = np.full((h, w, 3), 40, np.uint8)
    ring = fm.masks.get("chainring")
    if ring is not None and ring.any():
        img[ring] = (220, 220, 220)
    chain = fm.masks.get("chain")
    if chain is not None and chain.any():
        img[chain] = (80, 200, 80)
    return img


# ------------------------------------------------------- chemin réel (RPL-T2)


def read_video_frames(video_path):
    """Toutes les images BGR d'une vidéo + sa cadence (sync, OpenCV)."""
    import cv2
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"vidéo illisible : {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or FPS
    frames = []
    while True:
        ok, img = cap.read()
        if not ok:
            break
        frames.append(img)
    cap.release()
    if not frames:
        raise RuntimeError(f"vidéo vide : {video_path}")
    return frames, float(fps)


def keyframe_for(bgr, fm):
    """Gros plan autour du plateau pour Spark (recadré, jamais agrandi).

    Même `crop_around` que le direct (`fixloop/agent.py`) ; image entière si le
    plateau est absent ou aux mauvaises dimensions.
    """
    from fixloop.agent import crop_around
    ring = fm.masks.get("chainring")
    if ring is not None and ring.any() and ring.shape == bgr.shape[:2]:
        import numpy as np
        ys, xs = np.nonzero(ring)
        box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
        try:
            return crop_around(bgr, box)
        except Exception:
            pass
    return bgr


def encode_video(src, dest, fps: float = FPS, width: int = VIDEO_WIDTH,
                 keep_audio: bool = False) -> str:
    """Réencode la vidéo : H.264, ≤ 960 px, `+faststart`, sans piste audio (RPL-D5).

    Rend le codec écrit dans `meta.json` (`video_codec`). ffmpeg introuvable :
    copie OpenCV `opencv-mp4v` (tests) avec un avertissement, que
    `deploy_check.py` refuse de publier. ffmpeg présent mais en échec :
    `RuntimeError` avec la fin de stderr, jamais de copie OpenCV.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is not None:
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(src),
               "-vf", f"fps={fps},scale='min({width},iw)':-2",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
        if not keep_audio:
            cmd.append("-an")  # RPL-D5 : la voix ne va pas dans l'historique public
        result = subprocess.run(cmd + [str(dest)], capture_output=True)
        if result.returncode != 0:
            tail = result.stderr.decode("utf-8", "replace").strip().splitlines()[-5:]
            raise RuntimeError(f"ffmpeg en échec (code {result.returncode}) sur {src} :\n"
                               + "\n".join(tail))
        return VIDEO_CODEC
    print(f"avertissement : ffmpeg introuvable, copie OpenCV {OPENCV_CODEC} (illisible "
          f"sur téléphone, refusée par deploy_check.py) : {dest}", file=sys.stderr)
    import cv2
    cap = cv2.VideoCapture(str(src))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = cv2.VideoWriter(str(dest), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"écriture vidéo impossible : {dest}")
    while True:
        ok, img = cap.read()
        if not ok:
            break
        writer.write(img)
    cap.release()
    writer.release()
    return OPENCV_CODEC


def read_sam_cache(sam_dir, procedure) -> dict:
    """Relit les sorties brutes SAM sans aucun appel (mode `--offline`)."""
    from fixloop.perception import live_parts
    out = {}
    for part in live_parts(procedure):
        path = Path(sam_dir) / f"raw_{part}.txt"
        if not path.is_file():
            raise RuntimeError(f"SAM brut manquant hors ligne : {path} "
                               "(construire d'abord en ligne, RPL-T4)")
        out[part] = path.read_text(encoding="utf-8")
    return out


def fetch_sam_raws(video_path, procedure, sam_dir, client=None, prepare=None,
                   uploader=None, fps: float = FPS) -> dict:
    """Sorties brutes SAM d'une vidéo via `segment_video` (auteur, async).

    `segment_video` réutilise son cache par morceau (`raw_<pièce>_<nn>.txt` +
    `.key`, PERC-R3.5) ; les textes recollés `raw_<pièce>.txt` sont relus ici.
    """
    from fixloop.perception import live_parts, segment_video
    asyncio.run(segment_video(str(video_path), procedure, str(sam_dir),
                              client=client, prepare=prepare, uploader=uploader,
                              fps=fps))
    return read_sam_cache(sam_dir, procedure)


def frames_from_raws(merged: dict, h: int, w: int, fps: float, procedure) -> list:
    """Textes bruts SAM -> un FrameMasks par image (même code que le direct)."""
    from fixloop.perception import assemble_frames
    return assemble_frames(merged, h, w, fps, procedure.get("select", {}))


def drive_frames(procedure_id: str, procedures: dict, measures: list, keyframes: list,
                 done_at: list, diagnose_idx: list, debounce: int,
                 agent, memory, bike_id: str, out):
    """Session complète sur des mesures + images clés (chemin réel, sync).

    Même `Session` que le direct ; `diagnose` reçoit les images clés aux
    instants `diagnose_at`, chaque mesure son image clé (recadrée).
    """
    from fixloop.state_machine import Session
    session = Session(procedures, agent, memory, out, bike_id=bike_id,
                      debounce_frames=debounce)
    if hasattr(out, "session"):
        out.session = session  # TSOut : horodatage dès `start()` (replay)
    diag = [keyframes[i] for i in diagnose_idx if 0 <= i < len(keyframes)]
    session.start(diag)
    pending = sorted(done_at)
    for i, m in enumerate(measures):
        while pending and pending[0] <= m.t + 1e-9:
            session.on_user_done()
            pending.pop(0)
        session.on_measures(m, keyframes[i] if i < len(keyframes) else None)
    return session


def nearest_indices(times: list, wants: list) -> list:
    """Indices des images les plus proches des instants voulus."""
    return [min(range(len(times)), key=lambda i: abs(times[i] - t)) for t in wants]


def spark_for(agent: str, offline: bool, spark_inner, cache_path, procedure_id: str):
    """Agent de la session : règles seules, ou Spark réel/faux en cache."""
    from fixloop.cached_models import OfflineError
    if agent != "fixloop":
        return NoSparkAgent(procedure_id)
    if offline and spark_inner is None:
        try:
            entries = json.loads(Path(cache_path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            entries = {}
        if not entries:  # RPL-R2.4 : échec rapide, jamais de réponse inventée
            raise OfflineError(f"cache Spark vide ou absent hors ligne : {cache_path} "
                               "(construire d'abord en ligne, RPL-T4)")
        return CachedAgent(None, cache_path)  # cache seul, erreur si clé absente
    inner = spark_inner
    if inner is None:  # auteur, en ligne : le vrai Spark (clé serveur requise)
        from fixloop.agent import SparkAgent
        from fixloop.procedures import load_all
        try:
            inner = SparkAgent(load_all())
        except Exception as exc:
            raise RuntimeError(f"Spark réel injoignable (clé MODEL_API_KEY requise, "
                               f"RPL-T4) : {exc}")
    if inner is None:
        inner = CannedAgent(procedure_id)
    return CachedAgent(inner, cache_path)


def memory_for(memory, bikes_root, cache_dir, name: str, offline: bool):
    """Mémoire de la session, en cache fichier si un cache est donné."""
    inner = memory if memory is not None else WonderMemory(root=bikes_root)
    if cache_dir is None:
        return inner
    return CachedMemory(inner if not offline else None,
                        Path(cache_dir) / f"{name}.memory.json", root=bikes_root)


def collect_outputs(session, out, frames, keyframes, fps: float, overlay_every: int,
                    procedure) -> tuple:
    """Événements + overlays (contours 5 images/s max, RPL-D4)."""
    from fixloop.benchmark import classify_contact
    from fixloop.geometry import measure
    from fixloop.perception import mask_to_svg_path
    measures = [measure(fm, procedure) for fm in frames]
    overlays = []
    for i, (fm, m) in enumerate(zip(frames, measures)):
        if i % overlay_every:
            continue
        contact = m.contact.get(("chain", "chainring"))
        paths = {p: mask_to_svg_path(fm.masks[p]) for p in ("chain", "chainring")
                 if p in fm.masks and fm.masks[p] is not None and fm.masks[p].any()}
        overlays.append({"t": round(m.t, 2),
                         "parts": paths,
                         "contact": None if contact != contact else round(float(contact), 3),
                         "label": classify_contact(contact),
                         "verdict": session.verdict})
    events = sorted(session.log + out.events, key=lambda e: (e.get("t", 0.0)))
    for e in events:
        model_name = model_for(e)
        if model_name is not None:
            e["model"] = model_name
    return events, overlays


def write_session(out_dir, session_def: dict, procedure_id: str, events: list,
                  overlays: list, dims: dict, fps: float, agent: str,
                  session, mode: str, source: str, video_codec: str) -> dict:
    """Écrit `events.json`, `overlays.json`, `meta.json`, `index.json` (déterministe)."""
    from fixloop.procedures import load_all as _procedures
    out_dir, name = Path(out_dir), session_def["name"]
    dest = out_dir / name
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "events.json").write_text(json.dumps(events, ensure_ascii=False,
                                                 sort_keys=True, indent=1),
                                      encoding="utf-8")
    (dest / "overlays.json").write_text(json.dumps(
        {"fps": round(fps, 3), "w": dims["w"],
         "h": dims["h"], "frames": overlays},
        ensure_ascii=False, sort_keys=True), encoding="utf-8")
    steps = [{"id": s["id"], "instruction": s.get("instruction", "")}
             for s in _procedures()[procedure_id]["steps"]]
    meta = {"name": name, "title": session_def.get("title", name),
            "steps": steps,
            "filmed": session_def.get("filmed"), "source": source,
            "fps": fps, "debounce_frames": session_def.get("debounce_frames", 4),
            "bike_id": session_def.get("bike_id"), "demo_history": bool(session_def.get("demo_history")),
            "mode": mode, "video_codec": video_codec,
            "agent": agent, "built": datetime.now(timezone.utc).isoformat(),
            "model_calls": dict(session.model_calls),
            "steps_validated": list(session.steps_validated)}
    (dest / "meta.json").write_text(json.dumps(meta, ensure_ascii=False,
                                               sort_keys=True, indent=1),
                                    encoding="utf-8")
    write_index(out_dir)
    return {"dir": dest, "events": len(events), "overlays": len(overlays)}


def build_video(session_def: dict, out_dir, bikes_root="data/bikes", cache_dir=None,
                offline: bool = False, agent: str = "fixloop", memory=None,
                spark_inner=None, sam_client=None, raws_fn=None, prepare=None,
                uploader=None, sam_dir=None, keep_audio: bool = False) -> dict:
    """Construit depuis une vidéo filmée (source `video`, RPL-T2)."""
    from fixloop.geometry import measure
    from fixloop.procedures import load_all
    name = session_def["name"]
    if (not offline and raws_fn is None and sam_client is None
            and prepare is None and uploader is None):
        raise RuntimeError("source 'video' : vidéos et vrais modèles requis "
                           "(EVAL-T7 / RPL-T4, pas pour cette série)")
    video_path = Path(session_def.get("video") or "")
    if not video_path.is_file():
        raise RuntimeError(f"vidéo introuvable : {video_path} (RPL-T3, pas pour cette série)")
    if not session_def.get("filmed"):
        raise RuntimeError("date de tournage `filmed` requise (bandeau RPL-R5.1)")
    procedure_id = session_def.get("procedure", "chain_off_chainring")
    procedure = load_all()[procedure_id]
    debounce = session_def.get("debounce_frames", 4)
    sam_out = Path(sam_dir) if sam_dir is not None else Path(out_dir) / name / "sam"

    if offline:
        merged = read_sam_cache(sam_out, procedure)  # aucun appel
    elif raws_fn is not None:
        merged = raws_fn(video_path, procedure, sam_out)  # faux SAM (tests)
    else:
        merged = fetch_sam_raws(video_path, procedure, sam_out, client=sam_client,
                                prepare=prepare, uploader=uploader, fps=FPS)

    bgr_frames, _src_fps = read_video_frames(video_path)
    h, w = bgr_frames[0].shape[:2]
    frames = frames_from_raws(merged, h, w, FPS, procedure)
    if not frames:
        raise RuntimeError("aucune image segmentée (SAM muet sur toute la vidéo)")
    measures = [measure(fm, procedure) for fm in frames]
    keyframes = []
    for i, fm in enumerate(frames):
        bgr = bgr_frames[min(i, len(bgr_frames) - 1)]
        keyframes.append(keyframe_for(bgr, fm))

    if offline and agent == "fixloop" and cache_dir is None:
        raise RuntimeError("hors ligne avec --agent fixloop : --cache requis")
    cache_path = (Path(cache_dir) / f"{name}.models.json"
                  if cache_dir is not None else Path(out_dir) / f"{name}.models.json")
    model = spark_for(agent, offline, spark_inner, cache_path, procedure_id)
    mem = memory_for(memory, bikes_root, cache_dir, name, offline)
    out = TSOut()
    times = [m.t for m in measures]
    diag_at = session_def.get("diagnose_at") or [times[0], times[min(1, len(times) - 1)],
                                                 times[min(2, len(times) - 1)]]
    session = drive_frames(procedure_id, load_all(), measures, keyframes,
                           list(session_def.get("user_done", [])),
                           nearest_indices(times, [float(t) for t in diag_at]),
                           debounce, model, mem,
                           session_def.get("bike_id", "demo-velo"), out)
    codec = encode_video(video_path, Path(out_dir) / name / "video.mp4", fps=FPS,
                         keep_audio=keep_audio)
    events, overlays = collect_outputs(session, out, frames, keyframes, FPS,
                                       OVERLAY_EVERY, procedure)
    return write_session(out_dir, session_def, procedure_id, events, overlays,
                         {"w": w, "h": h}, FPS, agent, session,
                         f"vidéo {FPS:.0f} images/s, anti-rebond {debounce} (RPL-R5.2)",
                         "video", codec)


def read_recording(rec_dir) -> tuple:
    """Dossier `recording/` : images 1/s + sorties SAM brutes (format en docstring)."""
    import cv2
    rec_dir = Path(rec_dir)
    spec = {}
    spec_path = rec_dir / "frames.json"
    if spec_path.is_file():
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    paths = sorted((rec_dir / "frames").glob("*.jpg")) + sorted((rec_dir / "frames").glob("*.png"))
    if not paths:
        raise RuntimeError(f"enregistrement sans images : {rec_dir}/frames/")
    keyframes = [cv2.imread(str(p)) for p in paths]
    h, w = keyframes[0].shape[:2]
    fps = float(spec.get("fps", RECORDING_FPS))
    merged = {}
    for part_file in sorted(rec_dir.glob("raw_*.txt")):
        merged[part_file.stem[4:]] = part_file.read_text(encoding="utf-8")
    if not merged:
        raise RuntimeError(f"enregistrement sans sorties SAM : {rec_dir}/raw_*.txt")
    return keyframes, merged, {"w": spec.get("w", w), "h": spec.get("h", h), "fps": fps}


def build_recording(session_def: dict, out_dir, bikes_root="data/bikes", cache_dir=None,
                    offline: bool = False, agent: str = "fixloop", memory=None,
                    spark_inner=None) -> dict:
    """Construit depuis une session en direct enregistrée (source `recording`, RPL-T2)."""
    from fixloop.geometry import measure
    from fixloop.procedures import load_all
    name = session_def["name"]
    rec_dir = Path(session_def.get("recording") or "")
    if not rec_dir.is_dir():
        raise RuntimeError(f"enregistrement introuvable : {rec_dir} (RPL-T8, pas pour cette série)")
    if not session_def.get("filmed"):
        raise RuntimeError("date de tournage `filmed` requise (bandeau RPL-R5.1)")
    procedure_id = session_def.get("procedure", "chain_off_chainring")
    procedure = load_all()[procedure_id]
    debounce = session_def.get("debounce_frames", 3)
    keyframes, merged, spec = read_recording(rec_dir)
    fps = spec["fps"]
    frames = frames_from_raws(merged, spec["h"], spec["w"], fps, procedure)
    if not frames:
        raise RuntimeError("aucune image segmentée (enregistrement vide)")
    measures = [measure(fm, procedure) for fm in frames]

    if offline and agent == "fixloop" and cache_dir is None:
        raise RuntimeError("hors ligne avec --agent fixloop : --cache requis")
    cache_path = (Path(cache_dir) / f"{name}.models.json"
                  if cache_dir is not None else Path(out_dir) / f"{name}.models.json")
    model = spark_for(agent, offline, spark_inner, cache_path, procedure_id)
    mem = memory_for(memory, bikes_root, cache_dir, name, offline)
    out = TSOut()
    times = [m.t for m in measures]
    diag_at = session_def.get("diagnose_at") or times[:3]
    session = drive_frames(procedure_id, load_all(), measures, keyframes,
                           list(session_def.get("user_done", [])),
                           nearest_indices(times, [float(t) for t in diag_at]),
                           debounce, model, mem,
                           session_def.get("bike_id", "demo-velo"), out)
    dest = Path(out_dir) / name
    codec = encode_video_from_frames(keyframes, dest / "video.mp4", fps=fps)
    overlay_every = OVERLAY_EVERY if fps >= 10 else 1
    events, overlays = collect_outputs(session, out, frames, keyframes, fps,
                                       overlay_every, procedure)
    return write_session(out_dir, session_def, procedure_id, events, overlays,
                         {"w": spec["w"], "h": spec["h"]}, fps, agent, session,
                         f"session en direct enregistrée {fps:.0f} image/s, "
                         f"anti-rebond {debounce} (RPL-R5.2)",
                         "recording", codec)


def encode_video_from_frames(bgr_frames: list, dest, fps: float = RECORDING_FPS) -> str:
    """Vidéo du replay depuis les images enregistrées (source `recording`).

    Images écrites avec OpenCV dans un fichier temporaire, puis réencodées par
    `encode_video` : même codec et même garde-fou que la source `video` (RPL-D5).
    """
    import cv2
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    raw = dest.with_name("video.frames.mp4")
    h, w = bgr_frames[0].shape[:2]
    writer = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not writer.isOpened():
        raise RuntimeError(f"écriture vidéo impossible : {raw}")
    for img in bgr_frames:
        writer.write(img)
    writer.release()
    try:
        return encode_video(raw, dest, fps=fps)
    finally:
        raw.unlink(missing_ok=True)


def build(session_def: dict, out_dir, bikes_root="data/bikes", cache_dir=None,
          offline: bool = False, agent: str = "rules", memory=None,
          spark_inner=None, sam_client=None, raws_fn=None, prepare=None,
          uploader=None, sam_dir=None, keep_audio: bool = False) -> dict:
    """Construit `replay/build/<nom>/` depuis une description de session."""
    from fixloop.perception import mask_to_svg_path
    source = session_def.get("source", "synthetic")
    if source == "video":
        return build_video(session_def, out_dir, bikes_root=bikes_root,
                           cache_dir=cache_dir, offline=offline, agent=agent,
                           memory=memory, spark_inner=spark_inner,
                           sam_client=sam_client, raws_fn=raws_fn, prepare=prepare,
                           uploader=uploader, sam_dir=sam_dir, keep_audio=keep_audio)
    if source == "recording":
        return build_recording(session_def, out_dir, bikes_root=bikes_root,
                               cache_dir=cache_dir, offline=offline, agent=agent,
                               memory=memory, spark_inner=spark_inner)
    out_dir, name = Path(out_dir), session_def["name"]
    if source != "synthetic":
        raise RuntimeError(f"source {session_def.get('source')!r} : vidéos et vrais modèles "
                           "requis (EVAL-T7 / RPL-T4, pas pour cette série)")
    if offline and agent == "fixloop" and cache_dir is None:
        raise RuntimeError("hors ligne avec --agent fixloop : --cache requis")

    memory = WonderMemory(root=bikes_root)
    if agent == "fixloop":
        inner = None if offline else CannedAgent(session_def.get("procedure",
                                                                 "chain_off_chainring"))
        cache_path = (Path(cache_dir) / f"{name}.models.json"
                      if cache_dir is not None else out_dir / f"{name}.models.json")
        model = CachedAgent(inner, cache_path)
    else:
        model = NoSparkAgent(session_def.get("procedure", "chain_off_chainring"))
    out = TSOut()
    overlays = []
    dims: dict = {}
    writer: dict = {}

    def frame_writer(h, w):
        # mp4v en flux ; les vraies vidéos (RPL-T4) passeront par ffmpeg + faststart.
        import cv2
        if "w" not in writer:
            path = out_dir / name / "video.mp4"
            path.parent.mkdir(parents=True, exist_ok=True)
            writer["w"] = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"),
                                          FPS, (w, h))
            if not writer["w"].isOpened():
                raise RuntimeError(f"écriture vidéo impossible : {path}")
        return writer["w"]

    def visit(i, t, fm, m):
        img = render_frame(fm)
        if "h" not in dims:
            dims["h"], dims["w"] = img.shape[:2]
        frame_writer(dims["h"], dims["w"]).write(img)  # flux : jamais tout en RAM
        del img
        if i % OVERLAY_EVERY:
            return
        contact = m.contact.get(("chain", "chainring"))
        paths = {p: mask_to_svg_path(fm.masks[p]) for p in ("chain", "chainring")
                 if p in fm.masks and fm.masks[p] is not None and fm.masks[p].any()}
        overlays.append({"t": round(t, 2),
                         "parts": paths,
                         "contact": None if contact != contact else round(float(contact), 3),
                         "label": classify_contact(contact),
                         "verdict": out.session.verdict if out.session else "0"})

    try:
        session, _ = drive_session(session_def.get("procedure", "chain_off_chainring"),
                                   [tuple(s) for s in session_def["segments"]],
                                   list(session_def.get("user_done", [])), "replay",
                                   agent=model, memory=memory, out=out, visit=visit)
    finally:
        if "w" in writer:
            writer["w"].release()
    if "h" not in dims:
        raise RuntimeError("aucune image : segments vides ?")
    events = sorted(session.log + out.events, key=lambda e: (e.get("t", 0.0)))
    for e in events:
        model_name = model_for(e)
        if model_name is not None:
            e["model"] = model_name

    dest = out_dir / name
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "events.json").write_text(json.dumps(events, ensure_ascii=False,
                                                 sort_keys=True, indent=1),
                                      encoding="utf-8")
    (dest / "overlays.json").write_text(json.dumps(
        {"fps": FPS / OVERLAY_EVERY, "w": dims["w"],
         "h": dims["h"], "frames": overlays},
        ensure_ascii=False, sort_keys=True), encoding="utf-8")
    from fixloop.procedures import load_all as _procedures
    steps = [{"id": s["id"], "instruction": s.get("instruction", "")}
             for s in _procedures()[session_def.get("procedure",
                                                     "chain_off_chainring")]["steps"]]
    meta = {"name": name, "title": session_def.get("title", name),
            "steps": steps,
            "filmed": session_def.get("filmed"), "source": "synthetic",
            "fps": FPS, "debounce_frames": session_def.get("debounce_frames", 4),
            "bike_id": session_def.get("bike_id"), "demo_history": bool(session_def.get("demo_history")),
            "mode": "session synthétique 10 images/s, anti-rebond 4 (RPL-R5.2)",
            "agent": agent, "built": datetime.now(timezone.utc).isoformat(),
            "model_calls": dict(session.model_calls),
            "steps_validated": list(session.steps_validated)}
    (dest / "meta.json").write_text(json.dumps(meta, ensure_ascii=False,
                                               sort_keys=True, indent=1),
                                    encoding="utf-8")
    write_index(out_dir)
    return {"dir": dest, "events": len(events), "overlays": len(overlays)}


def write_index(out_dir) -> None:
    """`index.json` : sélecteur de session du lecteur."""
    out_dir = Path(out_dir)
    sessions = []
    for meta_path in sorted(out_dir.glob("*/meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        sessions.append({"name": meta["name"], "title": meta["title"],
                         "dir": meta_path.parent.name,
                         "filmed": meta.get("filmed"), "mode": meta.get("mode")})
    (out_dir / "index.json").write_text(json.dumps(sessions, ensure_ascii=False,
                                                   sort_keys=True, indent=1),
                                        encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Construit une session replay (RPL-T2).")
    ap.add_argument("session", help="fichier de session JSON (replay/sessions/<nom>.json)")
    ap.add_argument("--out", default="replay/build")
    ap.add_argument("--bikes-root", default="data/bikes")
    ap.add_argument("--cache", default=None)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--agent", default="rules", choices=["rules", "fixloop"])
    ap.add_argument("--sam-dir", default=None,
                    help="dossier des sorties brutes SAM (défaut : <out>/<nom>/sam)")
    ap.add_argument("--keep-audio", action="store_true",
                    help="garder la piste audio (RPL-D5 : sans son par défaut)")
    args = ap.parse_args()
    with open(args.session, encoding="utf-8") as fh:
        session_def = json.load(fh)
    info = build(session_def, args.out, bikes_root=args.bikes_root,
                 cache_dir=args.cache, offline=args.offline, agent=args.agent,
                 sam_dir=args.sam_dir, keep_audio=args.keep_audio)
    print(f"{session_def['name']} : {info['events']} événements, "
          f"{info['overlays']} overlays -> {info['dir']}")


if __name__ == "__main__":
    main()
