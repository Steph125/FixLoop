"""Commandes vocales (spec/04-memory-voice, VOX-R2).

`normalize` et `CommandDetector` : purs, sans réseau. Le pont Transcribe
(`VoiceBridge`, VOX-T3) appellera `feed` avec les transcriptions finales.
"""

from __future__ import annotations

import re
import unicodedata

COMMANDS = {  # design 04, section 2.2 : formes déjà normalisées
    "done": ["c est fait", "j ai fini", "fini", "termine", "c est bon"],
    "help": ["aide moi", "aide", "je n y arrive pas", "au secours"],
    "repeat": ["repete", "redis", "quoi", "pardon"],
}
_PRIORITY = ("done", "help", "repeat")  # si plusieurs commandes : done d'abord


def normalize(text: str) -> str:
    """Minuscules, sans accents, apostrophes et ponctuation en espaces (VOX-R2.1)."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class CommandDetector:
    """Détecte done/help/repeat dans les transcriptions finales (VOX-R2.1 à R2.4)."""

    def __init__(self, cooldown_s: float = 2.0, mute_tail_s: float = 0.5):
        self.cooldown_s = cooldown_s
        self.mute_tail_s = mute_tail_s
        self._speaking = False
        self.mute_until = 0.0
        self.last_trigger: dict[str, float] = {}
        self.history: list[dict] = []  # journal (transcription normalisée, VOX-T4)

    def speaking(self, on: bool, t: float) -> None:
        """Signalé par l'appli au début / à la fin de la synthèse vocale."""
        self._speaking = on
        if not on:
            self.mute_until = t + self.mute_tail_s

    def feed(self, final_text: str, t: float) -> str | None:
        """Rend "done" | "help" | "repeat" | None."""
        if self._speaking or t < self.mute_until:  # VOX-R2.4 : ne pas s'entendre
            return None
        padded = f" {normalize(final_text)} "
        for cmd in _PRIORITY:
            if any(f" {form} " in padded for form in COMMANDS[cmd]):
                if t - self.last_trigger.get(cmd, -1e9) < self.cooldown_s:  # VOX-R2.3
                    return None
                self.last_trigger[cmd] = t
                self.history.append({"t": t, "command": cmd, "text": normalize(final_text)})
                return cmd
        return None  # VOX-R2.2
