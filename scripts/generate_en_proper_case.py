#!/usr/bin/env python3
"""Build en_proper_case.txt.gz from LibreOffice's en_US.dic/.aff.

Source: https://github.com/LibreOffice/dictionaries/tree/master/en
"""
from __future__ import annotations

import argparse
import gzip
import re
import sys
from pathlib import Path


def read_affixes(aff_path: Path) -> dict[str, tuple[str, bool, list]]:
    """Parse PFX/SFX rules as {flag: (kind, cross_product, [(strip, add, cond)])}."""
    affixes: dict[str, tuple[str, bool, list]] = {}
    with aff_path.open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            parts = line.split()
            if len(parts) < 4 or parts[0] not in ("PFX", "SFX"):
                continue
            kind, flag = parts[0], parts[1]
            if flag not in affixes:
                # Header line: PFX A Y 1
                affixes[flag] = (kind, parts[2] == "Y", [])
                continue
            strip = "" if parts[2] == "0" else parts[2]
            add = "" if parts[3] == "0" else parts[3].split("/", 1)[0]
            cond = parts[4] if len(parts) > 4 else "."
            pattern = f"^{cond}" if kind == "PFX" else f"{cond}$"
            affixes[flag][2].append((strip, add, re.compile(pattern)))
    return affixes


def _apply(kind: str, rules: list, word: str) -> list[str]:
    forms = []
    for strip, add, cond in rules:
        if not cond.search(word):
            continue
        if kind == "SFX" and word.endswith(strip):
            forms.append(word[: len(word) - len(strip)] + add)
        elif kind == "PFX" and word.startswith(strip):
            forms.append(add + word[len(strip):])
    return forms


def expand(word: str, flags: str, affixes: dict) -> set[str]:
    """All surface forms Hunspell derives from word/flags (one prefix + one suffix)."""
    forms = {word}
    prefixed, suffixed = [], []
    for flag in flags:
        entry = affixes.get(flag)
        if entry is None:
            continue
        kind, cross, rules = entry
        for form in _apply(kind, rules, word):
            forms.add(form)
            if cross:
                (prefixed if kind == "PFX" else suffixed).append((form, rules))
    for flag in flags:
        entry = affixes.get(flag)
        if entry is None or entry[0] != "PFX" or not entry[1]:
            continue
        for form, _ in suffixed:
            forms.update(_apply("PFX", entry[2], form))
    return forms


def preferred_forms(dic_path: Path, aff_path: Path) -> dict[str, str]:
    affixes = read_affixes(aff_path)
    entries_cap: dict[str, str] = {}
    entries_low: set[str] = set()
    with dic_path.open(encoding="utf-8", errors="ignore") as handle:
        next(handle, None)  # word count
        for line in handle:
            raw = line.strip().split()
            if not raw:
                continue
            word, _, flags = raw[0].partition("/")
            if not word.isascii() or not word.isalpha():
                continue
            if word[0].isupper():
                # Simple TitleCase only (Iran), skip McDonald / NASA / etc.
                if len(word) > 1 and not word[1:].islower():
                    continue
                key = word.casefold()
                prev = entries_cap.get(key)
                if prev is None or len(word) < len(prev):
                    entries_cap[key] = word
            else:
                # Affixed forms count too: "as" is only listed as a/S.
                entries_low.update(form.casefold() for form in expand(word, flags, affixes))
    return {
        key: word
        for key, word in entries_cap.items()
        if key not in entries_low
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dic", type=Path, help="Path to en_US.dic")
    parser.add_argument(
        "--aff",
        type=Path,
        help="Path to en_US.aff (default: next to the .dic)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "src"
        / "jottr"
        / "editor"
        / "data"
        / "en_proper_case.txt.gz",
        help="Output .txt.gz path",
    )
    args = parser.parse_args(argv)
    forms = preferred_forms(args.dic, args.aff or args.dic.with_suffix(".aff"))
    payload = "\n".join(sorted(forms.values(), key=str.casefold)) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(gzip.compress(payload.encode("utf-8"), compresslevel=9))
    print(f"Wrote {len(forms)} forms to {args.output} ({args.output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
