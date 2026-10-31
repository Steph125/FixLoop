"""Historique de démonstration pour la vidéo (spec/04-memory-voice, MEM-T6).

Crée 2 chutes de chaîne (J-6, J-2) marquées `demo: true`, pour montrer la
mémoire et la phrase de panne répétée. Le README et la vidéo signalent que
cet historique est préparé (MEM-R4.2). Aucun réseau, aucun modèle appelé.

Usage : python scripts/seed_history.py [--bike demo-velo] [--root data/bikes]
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fixloop.memory import WonderMemory  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Crée un historique vélo de démonstration.")
    ap.add_argument("--bike", default="demo-velo", help="identifiant du vélo")
    ap.add_argument("--root", default="data/bikes", help="dossier des historiques")
    args = ap.parse_args()
    mem = WonderMemory(root=args.root)
    now = datetime.now(timezone.utc)
    for days_ago in (6, 2):
        mem.save(args.bike, {
            "procedure": "chain_off_chainring",
            "success": True,
            "date": (now - timedelta(days=days_ago)).isoformat(),
            "duration_s": 142,
            "steps_validated": ["frame_view", "engage_top_teeth", "turn_backward"],
            "anomalies": [],
            "model_calls": {"spark": 3, "wonder": 2},
            "demo": True,
        })
    n = mem.repeated(args.bike, "chain_off_chainring")
    print(f"historique démo écrit pour {args.bike} ({n} chutes en un mois)")


if __name__ == "__main__":
    main()
