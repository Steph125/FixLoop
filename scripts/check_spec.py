"""Contrôle de cohérence de la spécification (spec/README.md, section Conventions).

Vérifie, sans réseau :
1. chaque critère d'acceptation (PREFIX-Rn.m) est couvert par le tableau « Couverture » d'un tasks.md ;
2. chaque référence `PREFIX-Rn.m`, `PREFIX-Dn`, `PREFIX-Tn` citée dans spec/ existe ;
3. chaque tâche citée dans une couverture existe.

Usage : python scripts/check_spec.py   (code de sortie 1 s'il y a un problème)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "spec"
PREFIXES = "CORE|PERC|AGT|MEM|VOX|SRV|APP|RPL|EVAL|SUB"

REQ_HEAD = re.compile(rf"^## ({PREFIXES})-R(\d+) ")
ITEM = re.compile(r"^(\d+)\. ")
DEC = re.compile(rf"\*\*(({PREFIXES})-D\d+)")
TASK = re.compile(rf"\*\*(({PREFIXES})-T\d+) ")
REF = re.compile(rf"\b({PREFIXES})-(R\d+(?:\.\d+)?|D\d+|T\d+)\b")
RANGE = re.compile(r"(?:\b(" + PREFIXES + r")-)?R(\d+)(?:\.(\d+))?(?:\s*[–-]\s*R?(\d+)\.(\d+))?")


def parse_requirements() -> dict[str, set[str]]:
    """PREFIX -> ensemble des critères ('CORE-R3.4') ; une exigence sans critère numéroté compte pour un."""
    crit: dict[str, set[str]] = {}
    for f in sorted(SPEC.glob("*/requirements.md")):
        current = None
        has_items = False
        for line in f.read_text(encoding="utf-8").splitlines():
            m = REQ_HEAD.match(line)
            if m:
                if current and not has_items:
                    crit.setdefault(current[0], set()).add(f"{current[0]}-R{current[1]}")
                current, has_items = (m.group(1), m.group(2)), False
                continue
            if line.startswith("## ") or line.startswith("---"):
                if current and not has_items:
                    crit.setdefault(current[0], set()).add(f"{current[0]}-R{current[1]}")
                current = None
                continue
            m = ITEM.match(line)
            if current and m:
                has_items = True
                crit.setdefault(current[0], set()).add(f"{current[0]}-R{current[1]}.{m.group(1)}")
        if current and not has_items:
            crit.setdefault(current[0], set()).add(f"{current[0]}-R{current[1]}")
    return crit


def expand(cell: str, default: str | None, all_crit: set[str]) -> set[str]:
    out = set()
    for m in RANGE.finditer(cell):
        prefix = m.group(1) or default        # une forme courte « R1.3 » reprend le dernier préfixe écrit
        default = prefix
        if prefix is None:
            continue
        r, a = int(m.group(2)), m.group(3)
        if a is None:                                   # « R8 » : l'exigence entière
            out |= {c for c in all_crit if c == f"{prefix}-R{r}" or c.startswith(f"{prefix}-R{r}.")}
        elif m.group(4):                                # plage R1.1–R1.3 ou R1.1–R2.3
            r2, b = int(m.group(4)), int(m.group(5))
            for c in all_crit:
                mm = re.fullmatch(rf"{prefix}-R(\d+)\.(\d+)", c)
                if mm and (r, int(a)) <= (int(mm.group(1)), int(mm.group(2))) <= (r2, b):
                    out.add(c)
        else:
            out.add(f"{prefix}-R{r}.{a}")
    return out


def main() -> int:
    crit_by_prefix = parse_requirements()
    all_crit = set().union(*crit_by_prefix.values())
    texts = {f: f.read_text(encoding="utf-8") for f in SPEC.rglob("*.md")}
    decisions = {m.group(1) for t in texts.values() for m in DEC.finditer(t)}
    tasks = {m.group(1) for t in texts.values() for m in TASK.finditer(t)}
    problems: list[str] = []

    covered: set[str] = set()
    for f in sorted(SPEC.glob("*/tasks.md")):
        text = texts[f]
        default = (re.search(rf"\*\*({PREFIXES})-T", text) or [None, None])[1]
        cov = text.split("## Couverture", 1)
        if len(cov) < 2:
            problems.append(f"{f.relative_to(ROOT)} : pas de section « Couverture »")
            continue
        for line in cov[1].splitlines():
            if not line.startswith("|") or "---" in line or "Critère" in line:
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            # « R1.1 | T2 ; R1.3 : T5 » : les critères sont dans les deux colonnes, les tâches dans la seconde
            covered |= expand(" ".join(cells), default, all_crit)
            for tm in re.finditer(rf"(?:\b({PREFIXES})-)?T(\d+)\b", cells[-1]):
                tid = f"{tm.group(1) or default}-T{tm.group(2)}"
                if tid not in tasks:
                    problems.append(f"{f.relative_to(ROOT)} : tâche inconnue {tid} dans la couverture")

    for c in sorted(all_crit - covered):
        problems.append(f"critère non couvert par une tâche : {c}")

    for f, t in texts.items():
        for m in REF.finditer(t):
            ref = f"{m.group(1)}-{m.group(2)}"
            kind = m.group(2)[0]
            ok = (ref in decisions if kind == "D" else ref in tasks if kind == "T"
                  else ref in all_crit or any(c.startswith(ref + ".") for c in all_crit))
            if not ok:
                problems.append(f"{f.relative_to(ROOT)} : référence inconnue {ref}")

    n_req = len({c.split(".")[0] for c in all_crit})
    print(f"{n_req} exigences, {len(all_crit)} critères, {len(decisions)} décisions, {len(tasks)} tâches")
    for p in sorted(set(problems)):
        print("  -", p)
    print("OK" if not problems else f"{len(set(problems))} problème(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
