"""Vérifie un site replay assemblé avant déploiement (RPL-T9, préparation série 4).

Usage : python replay/deploy_check.py --site public
Ne déploie rien : le déploiement (`.github/workflows/pages.yml`, déclenché à la
main) et la vérification sur téléphone sont pour l'auteur (RPL-T9, pas pour
cette série). Sortie 0 si le site est publiable, 1 sinon.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ALLOWED_TOP = {"replay.html", "replay.js", "style.css", "lib.js"}
SESSION_FILES = {"video.mp4", "overlays.json", "events.json", "meta.json"}
OVERLAY_BUDGET = 2 * 1024 * 1024  # RPL-R7.1 : overlays.json sous 2 Mo


def check_build(site) -> list[str]:
    """Erreurs bloquantes pour la publication, [] si le site est publiable."""
    site = Path(site)
    errors = []
    for name in sorted(ALLOWED_TOP):
        if not (site / name).is_file():
            errors.append(f"fichier manquant : {name}")
    for name in ("replay.html", "replay.js"):
        path = site / name
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            for marker in ("http://", "https://"):
                if marker in text:
                    errors.append(f"appel externe dans {name} : {marker} (RPL-R1.4)")
    index = site / "build" / "index.json"
    if not index.is_file():
        return errors + ["build/index.json manquant"]
    try:
        sessions = json.loads(index.read_text(encoding="utf-8"))
    except ValueError as exc:
        return errors + [f"build/index.json illisible : {exc}"]
    if not sessions:
        errors.append("aucune session dans build/index.json")
    for entry in sessions:
        errors += check_session(site / "build" / entry.get("dir", ""), entry.get("name", "?"))
    return errors


def check_session(path: Path, name: str) -> list[str]:
    """Une session : 4 fichiers, JSON valides, vidéo lisible, overlays sous 2 Mo."""
    errors = []
    for name_file in sorted(SESSION_FILES):
        if not (path / name_file).is_file():
            errors.append(f"session {name} : {name_file} manquant")
    for doc in ("overlays.json", "events.json", "meta.json"):
        p = path / doc
        if p.is_file():
            try:
                json.loads(p.read_text(encoding="utf-8"))
            except ValueError as exc:
                errors.append(f"session {name} : {doc} illisible ({exc})")
    overlays = path / "overlays.json"
    if overlays.is_file() and overlays.stat().st_size > OVERLAY_BUDGET:
        errors.append(f"session {name} : overlays.json dépasse 2 Mo (RPL-R7.1)")
    video = path / "video.mp4"
    if video.is_file() and not video_readable(video):
        errors.append(f"session {name} : video.mp4 illisible")
    return errors


def video_readable(path: Path) -> bool:
    """Au moins une image décodable (pas de mesure de performance ici)."""
    import cv2
    cap = cv2.VideoCapture(str(path))
    ok, _ = cap.read()
    cap.release()
    return bool(ok)


def main() -> None:
    ap = argparse.ArgumentParser(description="Vérifie un site replay avant déploiement.")
    ap.add_argument("--site", default="public")
    args = ap.parse_args()
    errors = check_build(args.site)
    if errors:
        print("site NON publiable :")
        for e in errors:
            print(f"- {e}")
        raise SystemExit(1)
    print(f"site publiable : {args.site}")


if __name__ == "__main__":
    main()
