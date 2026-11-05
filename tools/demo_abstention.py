"""Run the real recommendation gate in an isolated, disposable audit directory."""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="cwm-demo-") as temporary:
        base = [sys.executable, "-m", "cwm", "--audit", str(Path(temporary) / "audit"),
                "--uscita", str(Path(temporary) / "results")]
        print("CWM research prototype — actual engine, bundled example, synthetic preferences.", flush=True)
        for use in ("pilota_valutato", "raccomandazione_nazionale"):
            print(f"\nRequested use: {use}", flush=True)
            result = subprocess.run(base + ["raccomanda", "--uso", use], cwd=ROOT)
            if result.returncode != 2:
                print(f"DEMO FAILED: expected refusal (exit 2), got {result.returncode}.", file=sys.stderr)
                return 1
        print("\nVerified: both recommendations were withheld. This is not policy validation.")
        print("The evidence gate and final permission to recommend are different checks.")
        print("Audit keys and temporary results are removed; no telemetry is sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
