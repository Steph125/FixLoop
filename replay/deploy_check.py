"""Vérifie un site replay assemblé avant déploiement (RPL-T9, RPL-T11).

Usage : python replay/deploy_check.py --site public
Ne déploie rien : le déploiement (`.github/workflows/pages.yml`, déclenché à la
main) et la vérification sur téléphone sont pour l'auteur (RPL-T9, pas pour
cette série). Sortie 0 si le site est publiable, 1 sinon.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ALLOWED_TOP = {"replay.html", "index.html", "replay.js", "style.css", "lib.js"}
SESSION_FILES = {"video.mp4", "overlays.json", "events.json", "meta.json"}
OVERLAY_BUDGET = 2 * 1024 * 1024  # RPL-R7.1 : overlays.json sous 2 Mo
VIDEO_BUDGET = 15 * 1024 * 1024  # RPL-R7.1 : vidéo de plus de 15 Mo refusée
FORBIDDEN_NAMES = {".env"}  # RPL-R8.2 : ni .env, ni clé, ni journal
FORBIDDEN_SUFFIXES = {".jsonl"}  # journaux de session et de coûts

# Appels externes interdits (RPL-R1.4) : fetch/src/import vers http(s).
# Les liens `href="https://…"` (RPL-R7.2, depuis links.json) restent acceptés.
EXTERNAL_PATTERNS = (
    re.compile(r"""\bfetch\s*\(\s*["']https?://"""),
    re.compile(r"""\bsrc\s*=\s*["']https?://"""),
    re.compile(r"""\bfrom\s*["']https?://"""),
    re.compile(r"""\bimport\s*\(\s*["']https?://"""),
    re.compile(r"""@import\s+["']https?://"""),
)


def external_calls(text: str) -> list[str]:
    """Motifs d'appel externe trouvés dans un source HTML/JS."""
    return [p.pattern for p in EXTERNAL_PATTERNS if p.search(text)]


def check_build(site) -> list[str]:
    """Erreurs bloquantes pour la publication, [] si le site est publiable."""
    site = Path(site)
    errors = []
    if not (site / "replay.html").is_file() and not (site / "index.html").is_file():
        errors.append("fichier manquant : replay.html ou index.html (RPL-T11)")
    for name in ("replay.js", "style.css", "lib.js"):
        if not (site / name).is_file():
            errors.append(f"fichier manquant : {name}")
    for name in ("replay.html", "index.html", "replay.js"):
        path = site / name
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            for pattern in external_calls(text):
                errors.append(f"appel externe dans {name} : {pattern} (RPL-R1.4)")
    errors += check_forbidden(site)
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


def check_forbidden(site: Path) -> list[str]:
    """Ni `.env`, ni clé, ni journal de session dans le site (RPL-R8.2, RPL-T11)."""
    errors = []
    for path in sorted(site.rglob("*")):
        if not path.is_file():
            continue
        if path.name in FORBIDDEN_NAMES:
            errors.append(f"fichier interdit : {path.name} (RPL-R8.2)")
        if path.suffix in FORBIDDEN_SUFFIXES:
            errors.append(f"journal interdit : {path.name} (RPL-R8.2)")
        if path.stat().st_size > 32 * 1024 * 1024:
            continue  # trop gros pour une lecture texte : la règle vidéo s'en charge
        try:
            text = path.read_text(encoding="utf-8")
        except (ValueError, OSError):
            continue  # binaire (vidéo) : pas du texte à inspecter
        if "MODEL_API_KEY" in text:
            errors.append(f"clé API dans {path.name} (RPL-R8.2)")
    return errors


def check_session(path: Path, name: str) -> list[str]:
    """Une session : 4 fichiers, JSON valides, vidéo ≤ 15 Mo et lisible, overlays sous 2 Mo."""
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
    if video.is_file():
        if video.stat().st_size > VIDEO_BUDGET:
            errors.append(f"session {name} : video.mp4 dépasse 15 Mo (RPL-R7.1)")
        elif not video_readable(video):
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
