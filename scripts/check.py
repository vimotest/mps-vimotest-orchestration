#!/usr/bin/env python3
"""
Lightweight consistency checks for the orchestration repo (stdlib only, no MPS needed).

Usage:
  scripts/check.py            # offline checks (repos.json, .gitmodules, submodule markers)
  scripts/check.py --remote   # additionally verify fallback release URLs resolve
"""

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYNCED_SCRIPTS = ["download-mps.gradle", "run-mps-ant.gradle", "init-gradle-scripts.gradle"]
GRADLE_VERSION = "8.10.2"

errors: list = []


def fail(msg: str) -> None:
    errors.append(msg)
    print(f"::error::{msg}")


def section(title: str) -> None:
    print(f"\n== {title}")


def check_config(config: dict) -> None:
    section("repos.json vs .gitmodules")
    repos = config["repos"]
    out = subprocess.run(
        ["git", "config", "-f", ".gitmodules", "--get-regexp", r"^submodule\..*\.(path|url)$"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    mods: dict = {}
    for line in out.splitlines():
        key, val = line.split(" ", 1)
        name, field = key[len("submodule."):].rsplit(".", 1)
        mods.setdefault(name, {})[field] = val
    by_path = {m["path"]: m for m in mods.values()}

    for r in repos:
        m = by_path.get(r["path"])
        if not m:
            fail(f"{r['id']}: missing in .gitmodules")
        elif m["url"] != r["url"]:
            fail(f"{r['id']}: url mismatch (.gitmodules={m['url']} repos.json={r['url']})")
    for p in by_path:
        if p not in {r["path"] for r in repos}:
            fail(f".gitmodules path '{p}' not listed in repos.json")

    section("dependency order")
    order = {r["id"]: r["order"] for r in repos}
    if len(set(order.values())) != len(order):
        fail("duplicate 'order' values in repos.json")
    for r in repos:
        for dep in r.get("dependencies", []):
            if dep not in order:
                fail(f"{r['id']}: unknown dependency '{dep}'")
            elif order[dep] >= r["order"]:
                fail(f"{r['id']}: dependency '{dep}' must have a lower order")
        if bool(r.get("pluginProperty")) != bool(r.get("artifactZip")):
            fail(f"{r['id']}: pluginProperty and artifactZip must be set together")

    section("AGENTS.md table vs repos.json")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for r in repos:
        if f"`{r['id']}`" not in agents:
            fail(f"{r['id']}: not mentioned in AGENTS.md")


def check_submodules(config: dict) -> None:
    section("submodule migration markers")
    target_mps = config["targetMpsVersion"]
    target_build = config["targetIdeaSinceBuild"]
    src_gradle = ROOT / "mps-gradle-scripts" / "gradle"
    for r in config["repos"]:
        p = ROOT / r["path"]
        if not (p / "build.gradle").exists():
            fail(f"{r['id']}: submodule not checked out (run with submodules: true)")
            continue
        bg = (p / "build.gradle").read_text(encoding="utf-8")
        if not re.search(rf'ext\.mpsVersion\s*=\s*"{re.escape(target_mps)}"', bg):
            fail(f"{r['id']}: build.gradle does not set ext.mpsVersion = \"{target_mps}\"")

        wrapper = p / "gradle" / "wrapper" / "gradle-wrapper.properties"
        if not wrapper.exists() or f"gradle-{GRADLE_VERSION}-" not in wrapper.read_text(encoding="utf-8"):
            fail(f"{r['id']}: Gradle wrapper is not {GRADLE_VERSION}")

        mig = p / ".mps" / "migration.xml"
        if r["id"] != "mps-gradle-scripts":  # plain Gradle tooling repo, no MPS project
            if not mig.exists() or f'project.migrated.version" value="{target_build}"' not in mig.read_text(encoding="utf-8"):
                fail(f"{r['id']}: .mps/migration.xml is not migrated to {target_build}")

        if r["id"] != "mps-gradle-scripts":
            for s in SYNCED_SCRIPTS:
                dst = p / "gradle" / s
                if dst.exists() and dst.read_bytes() != (src_gradle / s).read_bytes():
                    fail(f"{r['id']}: gradle/{s} differs from mps-gradle-scripts (run ./orchestrate sync-scripts)")


def check_release_urls(config: dict) -> None:
    section("fallback release URLs (from build.gradle)")
    urls = set()
    for r in config["repos"]:
        bg = ROOT / r["path"] / "build.gradle"
        if bg.exists():
            urls.update(re.findall(r'"(https://github\.com/[^"]+/releases/download/[^"]+)"', bg.read_text(encoding="utf-8")))
    if not urls:
        fail("no fallback release URLs found in any build.gradle")
    for u in sorted(urls):
        try:
            req = urllib.request.Request(u, method="HEAD")
            with urllib.request.urlopen(req, timeout=30) as resp:
                print(f"OK   {resp.status} {u}")
        except Exception as e:
            fail(f"release URL not reachable: {u} ({e})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--remote", action="store_true", help="also check release URLs over the network")
    args = ap.parse_args()
    config = json.loads((ROOT / "repos.json").read_text(encoding="utf-8"))
    check_config(config)
    check_submodules(config)
    if args.remote:
        check_release_urls(config)
    print(f"\n{len(errors)} problem(s) found." if errors else "\nAll checks passed.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
