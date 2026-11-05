"""Save aggregate GitHub metrics using an existing gh login; never posts anything."""
import argparse
import datetime
import json
import subprocess
from pathlib import Path

REPO = "webcixonline-spec/collective-wisdom-model"


def snapshot(traffic=False):
    endpoints = {"repository": f"repos/{REPO}"}
    if traffic:
        endpoints.update({name: f"repos/{REPO}/traffic/{path}" for name, path in
                          (("views", "views"), ("clones", "clones"),
                           ("referrers", "popular/referrers"))})
    data = {"captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "repository": REPO, "metrics": {}, "errors": {}}
    for name, endpoint in endpoints.items():
        result = subprocess.run(["gh", "api", endpoint], capture_output=True, text=True)
        if result.returncode:
            data["errors"][name] = "Request failed; check gh authentication, permissions and rate limits."
            continue
        payload = json.loads(result.stdout)
        if name == "repository":
            payload = {k: payload[k] for k in ("stargazers_count", "forks_count", "open_issues_count")}
        data["metrics"][name] = payload
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traffic", action="store_true", help="Requires repository traffic access")
    parser.add_argument("--out", type=Path, required=True, help="New local JSON file; never overwritten")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Output exists; choose a new snapshot filename")
    try:
        data = snapshot(args.traffic)
    except FileNotFoundError:
        parser.error("GitHub CLI (gh) is required; authenticate locally before running")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    print(f"Saved {args.out}; {len(data['errors'])} unavailable metric groups.")
    return 1 if data["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
