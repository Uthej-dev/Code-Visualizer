"""Regenerate the frontend test fixtures from the real execution engine.

    cd backend && .venv/bin/python scripts/export_fixtures.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.samples import load_samples  # noqa: E402
from app.sandbox import run_code  # noqa: E402

OUT = ROOT.parent / "frontend" / "src" / "test" / "fixtures"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    samples = {s["id"]: s["code"] for s in load_samples()}
    fixtures = {
        "factorial": samples["factorial"],
        "modify-list": samples["modify-list"],
        "error": samples["error"],
        "syntax-error": "x = 1\nif x > 0\n    print(x)\n",
    }
    for name, code in fixtures.items():
        result = run_code(code)
        result["stats"]["durationMs"] = 0
        (OUT / f"{name}.json").write_text(json.dumps({"code": code, "trace": result}, indent=1) + "\n")
        print(f"wrote {name}.json ({len(result['steps'])} steps, status={result['status']})")


if __name__ == "__main__":
    main()
