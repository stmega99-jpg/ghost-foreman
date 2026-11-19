"""Build the folder that is published as the public demo site (GitHub Pages).

Only the files the demo page needs are copied, from an explicit list. Nothing else from the repository (backend,
data, tests, documents, agents, the older single-file screen) ever reaches the site. The site keeps the same relative
layout as the repository, because demo/index.html loads ../ui/dist/index.mjs and ../ui/m/vendor/react.mjs.

Usage: python scripts/build_demo_site.py [output-dir]      (default: _site)
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The complete list of published files. Add to it only when the demo page itself needs a new file.
PUBLISHED = (
    "demo/index.html",
    "demo/engine.mjs",
    "demo/sdk.mjs",
    "ui/dist/index.mjs",
    "ui/m/vendor/react.mjs",
)
ROOT_INDEX = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Ghost Foreman demo</title>
<meta http-equiv="refresh" content="0; url=demo/index.html"></head>
<body><p><a href="demo/index.html">Open the Ghost Foreman demo (sample data)</a></p></body></html>
"""


def build(out: Path) -> list[str]:
    """Write the site into *out* (emptied first) and return the sorted list of files written."""
    if out.exists():
        shutil.rmtree(out)
    for rel in PUBLISHED:
        src = ROOT / rel
        if not src.is_file():
            raise SystemExit(f"missing file for the demo site: {rel}")
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    (out / "index.html").write_text(ROOT_INDEX, encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")  # serve the files exactly as they are
    return sorted(str(p.relative_to(out)).replace("\\", "/") for p in out.rglob("*") if p.is_file())


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site"
    for name in build(out):
        print(name)


if __name__ == "__main__":
    main()