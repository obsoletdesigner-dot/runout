"""Lists missing and obsolete entries in each translation file of runout/locales/.

Usage: python tools/i18n_check.py [--write]

It collects every string passed to tr(), tr_n() or N_() in the code, plus the labels,
help texts, sections and choices of runout/core/fields.py. With --write, missing
entries are added to each file with an empty value (shown in English until translated)
and obsolete entries are removed.
"""
import ast
import glob
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from runout.core import fields  # noqa: E402
from runout.i18n import LOCALES_DIR  # noqa: E402

MARKERS = {"tr", "tr_n", "N_"}


def _literal(node):
    """Value of a string literal, including implicit concatenation."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def strings_in_code() -> set[str]:
    found = set()
    for path in glob.glob(os.path.join(ROOT, "runout", "**", "*.py"), recursive=True):
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) in MARKERS:
                for arg in node.args:
                    text = _literal(arg)
                    if text:
                        found.add(text)
    return found


def strings_in_fields() -> set[str]:
    found = set(fields.TABS) | set(fields.PICTURE_TYPES.values())
    for f in fields.FIELDS:
        found.add(f.label)
        if f.help:
            found.add(f.help)
        found.update(label for _, label in f.choices if label)
    return found


def main() -> int:
    wanted = strings_in_code() | strings_in_fields()
    write = "--write" in sys.argv
    status = 0
    for path in sorted(glob.glob(os.path.join(LOCALES_DIR, "*.json"))):
        with open(path, encoding="utf-8") as fh:
            catalog = json.load(fh)
        keys = {k for k in catalog if not k.startswith("_")}
        missing = sorted(wanted - {k for k in keys if catalog[k]})
        obsolete = sorted(keys - wanted)
        print("%s: %d entries, %d missing, %d obsolete"
              % (os.path.basename(path), len(keys), len(missing), len(obsolete)))
        for text in missing:
            print("  missing:  %r" % text)
        for text in obsolete:
            print("  obsolete: %r" % text)
        if missing or obsolete:
            status = 1
        if write:
            for text in missing:
                catalog.setdefault(text, "")
            for text in obsolete:
                del catalog[text]
            meta = {k: v for k, v in catalog.items() if k.startswith("_")}
            body = {k: catalog[k] for k in sorted(catalog) if not k.startswith("_")}
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({**meta, **body}, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
    return status


if __name__ == "__main__":
    sys.exit(main())
