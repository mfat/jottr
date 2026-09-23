#!/usr/bin/env python3
"""Build en_proper_case.txt.gz from a Hunspell/LibreOffice en_US.dic."""
from __future__ import annotations

import argparse
import gzip
import sys
from pathlib import Path


def preferred_forms(dic_path: Path) -> dict[str, str]:
    entries_cap: dict[str, str] = {}
    entries_low: set[str] = set()
    with dic_path.open(encoding="utf-8", errors="ignore") as handle:
        next(handle, None)  # word count
        for line in handle:
            raw = line.split("/", 1)[0].strip().split()
            if not raw:
                continue
            word = raw[0]
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
                entries_low.add(word.casefold())
    return {
        key: word
        for key, word in entries_cap.items()
        if key not in entries_low
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dic", type=Path, help="Path to en_US.dic")
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
    forms = preferred_forms(args.dic)
    payload = "\n".join(sorted(forms.values(), key=str.casefold)) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(gzip.compress(payload.encode("utf-8"), compresslevel=9))
    print(f"Wrote {len(forms)} forms to {args.output} ({args.output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
