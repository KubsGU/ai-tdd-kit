"""Compare controller response bytes without AI calls or reusing test results."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from smoke_demo import run_demo

KIT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="ai-tdd-context-") as folder:
        root = Path(folder)
        run_demo(root)
        path = root / ".ai-tdd/state.json"
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        calls = [sys.executable, "-B", str(KIT / "plugins/ai-tdd/scripts/tdd.py"), "--root", str(root)]
        compact = subprocess.check_output(calls + ["status"])
        full = subprocess.check_output(calls + ["--full", "status"])
        assert json.loads(compact)["receipt_current"] and json.loads(full)["receipt_current"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == before
        print(json.dumps({"phase": "DONE", "compact_bytes": len(compact), "full_bytes": len(full),
                          "response_byte_reduction": round(1-len(compact)/len(full), 6), "state_preserved": True,
                          "note": "Response bytes, not token counts or an AI cost/speed benchmark. Both status calls inspect current artifacts without executing the runner."}, indent=2))


if __name__ == "__main__":
    main()
