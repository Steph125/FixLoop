"""Publie des sessions replay sur GitHub Pages (préparation, RPL-T11).

Usage : python replay/publish.py <sessions…> [--build-dir replay/build]
       [--published-dir replay/published] [--video URL] [--live URL]

Copie les sessions choisies de `replay/build/` (ignoré par git) vers
`replay/published/` (suivi par git), écrit `index.json` (ces sessions
seulement) et `links.json` (`repo`, `benchmark`, `video` et `live`
facultatifs, lus par le lecteur, RPL-T7). Ne déclenche aucun workflow :
le déploiement (`.github/workflows/pages.yml`, manuel) et la vérification
sur téléphone sont pour l'auteur (RPL-T9).
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO = "https://github.com/Steph125/FixLoop"
BENCHMARK_URL = REPO + "/blob/main/eval/benchmark/report.md"
SESSION_FILES = ("video.mp4", "overlays.json", "events.json", "meta.json")


def publish(names, build_dir="replay/build", published_dir="replay/published",
            video=None, live=None) -> dict:
    """Copie `names` vers le dossier publié + `index.json` + `links.json`."""
    build_dir, published_dir = Path(build_dir), Path(published_dir)
    published_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for name in names:
        src = build_dir / name
        for leaf in SESSION_FILES:
            if not (src / leaf).is_file():
                raise RuntimeError(f"session {name} incomplète : {leaf} "
                                   f"manquant dans {src} (construire d'abord, RPL-T2)")
        dest = published_dir / name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest,
                        ignore=shutil.ignore_patterns("sam"))  # bruts SAM : jamais publiés
        meta = json.loads((dest / "meta.json").read_text(encoding="utf-8"))
        index.append({"name": meta["name"], "title": meta["title"],
                      "dir": dest.name, "filmed": meta.get("filmed"),
                      "mode": meta.get("mode")})
    (published_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False,
                                                         sort_keys=True, indent=1),
                                              encoding="utf-8")
    links = {"repo": REPO, "benchmark": BENCHMARK_URL}
    if video is not None:
        links["video"] = video
    if live is not None:
        links["live"] = live
    (published_dir / "links.json").write_text(json.dumps(links, ensure_ascii=False,
                                                         sort_keys=True, indent=1),
                                              encoding="utf-8")
    return {"dir": published_dir, "sessions": list(names), "links": links}


def main() -> None:
    ap = argparse.ArgumentParser(description="Prépare la publication Pages (RPL-T11).")
    ap.add_argument("sessions", nargs="+", help="noms des sessions à publier")
    ap.add_argument("--build-dir", default="replay/build")
    ap.add_argument("--published-dir", default="replay/published")
    ap.add_argument("--video", default=None, help="URL de la vidéo de démonstration")
    ap.add_argument("--live", default=None, help="URL du direct (s'il est ouvert)")
    args = ap.parse_args()
    info = publish(args.sessions, build_dir=args.build_dir,
                   published_dir=args.published_dir,
                   video=args.video, live=args.live)
    print(f"{len(info['sessions'])} session(s) -> {info['dir']} "
          f"(liens : {', '.join(sorted(info['links']))})")


if __name__ == "__main__":
    main()
