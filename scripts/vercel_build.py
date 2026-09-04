#!/usr/bin/env python3
"""Build the Vite frontend into ./public for Vercel CDN + SPA fallback."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
PUBLIC = ROOT / "public"
DIST = FRONTEND / "dist"


def main() -> int:
    if not (FRONTEND / "package.json").is_file():
        print("frontend/package.json missing", file=sys.stderr)
        return 1

    npm = shutil.which("npm")
    if not npm:
        print("npm not found on PATH", file=sys.stderr)
        return 1

    print("==> npm ci")
    subprocess.check_call([npm, "ci"], cwd=FRONTEND)
    print("==> npm run build")
    subprocess.check_call([npm, "run", "build"], cwd=FRONTEND)

    if not DIST.is_dir():
        print(f"build output missing: {DIST}", file=sys.stderr)
        return 1

    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    shutil.copytree(DIST, PUBLIC)
    print(f"==> copied {DIST} -> {PUBLIC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
