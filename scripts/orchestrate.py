#!/usr/bin/env python3
"""
ViMoTest MPS Hybrid Orchestration Tool

Coordinates migration of decentralized JetBrains MPS repositories to MPS 2026.1
via git submodules, automated script synchronization, and MCP (Model Context Protocol).
"""

import os
import sys
import json
import re
import shutil
import subprocess
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT_DIR / "repos.json"

def load_config() -> Dict[str, Any]:
    if not CONFIG_FILE.exists():
        print(f"Error: Config file not found at {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def run_cmd(cmd: List[str], cwd: Optional[Path] = None, check: bool = False, capture_output: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else str(ROOT_DIR),
        capture_output=capture_output,
        text=True,
        check=check
    )

def get_repo_by_id(config: Dict[str, Any], repo_id: str) -> Optional[Dict[str, Any]]:
    for repo in config["repos"]:
        if repo["id"] == repo_id or repo["name"].lower() == repo_id.lower() or repo["path"].lower() == repo_id.lower():
            return repo
    return None

def inspect_repo(repo: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    repo_path = ROOT_DIR / repo["path"]
    status: Dict[str, Any] = {
        "id": repo["id"],
        "order": repo["order"],
        "name": repo["name"],
        "path": repo["path"],
        "exists": repo_path.exists(),
        "is_git": (repo_path / ".git").exists(),
        "branch": None,
        "commit": None,
        "dirty": False,
        "mps_version": None,
        "scripts_has_2026": False,
        "idea_version_ok": False,
        "stage": "NOT_CLONED"
    }

    if not status["exists"] or not status["is_git"]:
        return status

    # Git info
    res = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)
    if res.returncode == 0:
        status["branch"] = res.stdout.strip()
    res = run_cmd(["git", "rev-parse", "--short", "HEAD"], cwd=repo_path)
    if res.returncode == 0:
        status["commit"] = res.stdout.strip()
    res = run_cmd(["git", "status", "--porcelain"], cwd=repo_path)
    if res.returncode == 0:
        status["dirty"] = bool(res.stdout.strip())

    # Check build.gradle
    build_gradle = repo_path / "build.gradle"
    if build_gradle.exists():
        content = build_gradle.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r'ext\.mpsVersion\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            status["mps_version"] = match.group(1)

    # Check gradle/download-mps.gradle
    download_gradle = repo_path / "gradle" / "download-mps.gradle"
    if download_gradle.exists():
        content = download_gradle.read_text(encoding="utf-8", errors="ignore")
        if f'"{config["targetMpsVersion"]}"' in content or f"'{config['targetMpsVersion']}'" in content:
            status["scripts_has_2026"] = True

    # Check idea-version in build scripts or models
    target_since = config.get("targetIdeaSinceBuild", "261")
    idea_ok = False
    for p in repo_path.glob("solutions/**/*.mps"):
        try:
            if target_since in p.read_text(encoding="utf-8", errors="ignore"):
                idea_ok = True
                break
        except Exception:
            pass
    if not idea_ok:
        for p in repo_path.glob("**/build.xml"):
            try:
                if target_since in p.read_text(encoding="utf-8", errors="ignore"):
                    idea_ok = True
                    break
            except Exception:
                pass
    status["idea_version_ok"] = idea_ok

    # Determine stage
    target_mps = config["targetMpsVersion"]
    if status["mps_version"] == target_mps and status["scripts_has_2026"]:
        bundle = repo_path / "build" / "mps-bundle"
        if bundle.exists():
            status["stage"] = "PREPARED"
        else:
            status["stage"] = "SCRIPTS_UPDATED"
    elif status["exists"]:
        status["stage"] = "CLONED"

    return status

def cmd_status(args: argparse.Namespace) -> None:
    config = load_config()
    target_mps = config["targetMpsVersion"]
    print("=" * 86)
    print(f" ViMoTest MPS Migration Orchestrator -> Target MPS: {target_mps} (JBR {config['targetJbrVersion']})")
    print("=" * 86)
    print(f"{'#':<3} {'Repository':<26} {'Submodule':<12} {'MPS Ver':<10} {'Scripts':<10} {'Stage':<16} {'Git Ref':<10}")
    print("-" * 86)

    all_statuses = [inspect_repo(repo, config) for repo in config["repos"]]

    for st in all_statuses:
        submod_str = "Cloned" if st["is_git"] else "Missing"
        mps_str = st["mps_version"] or "-"
        scripts_str = "2026.1 OK" if st["scripts_has_2026"] else "Outdated"
        if not st["exists"]:
            scripts_str = "-"
        stage_str = st["stage"]
        if st["dirty"]:
            stage_str += "*"
        ref_str = f"{st['branch'] or ''}@{st['commit'] or ''}" if st["commit"] else "-"

        print(f"{st['order']:<3} {st['id']:<26} {submod_str:<12} {mps_str:<10} {scripts_str:<10} {stage_str:<16} {ref_str:<10}")

    print("-" * 86)
    print("Stages: NOT_CLONED -> CLONED -> SCRIPTS_UPDATED -> PREPARED -> TESTED -> RELEASED")
    print("(*) Indicates uncommitted working directory changes")
    print("=" * 86)

def cmd_next(args: argparse.Namespace) -> None:
    config = load_config()
    target_mps = config["targetMpsVersion"]
    all_statuses = {st["id"]: st for st in [inspect_repo(repo, config) for repo in config["repos"]]}

    for repo in config["repos"]:
        st = all_statuses[repo["id"]]
        # Check if dependencies are ready
        deps_ready = True
        for dep in repo.get("dependencies", []):
            dep_st = all_statuses.get(dep)
            if not dep_st or dep_st["stage"] not in ["SCRIPTS_UPDATED", "PREPARED", "TESTED", "RELEASED"]:
                deps_ready = False
                break

        if not deps_ready:
            continue

        if st["mps_version"] != target_mps or not st["scripts_has_2026"] or st["stage"] == "NOT_CLONED":
            print(f"Next repo to migrate: #{repo['order']} '{repo['id']}' ({repo['name']})")
            print(f"  Description: {repo.get('description', '')}")
            print(f"  Dependencies: {', '.join(repo.get('dependencies', [])) or 'None'}")
            print(f"  Current Status: {st['stage']}, MPS {st['mps_version'] or 'N/A'}")
            return

    print("All repositories are up-to-date with target MPS version!")

def cmd_init(args: argparse.Namespace) -> None:
    config = load_config()
    target = args.repo.lower() if args.repo else "all"

    for repo in config["repos"]:
        if target != "all" and repo["id"].lower() != target and repo["path"].lower() != target:
            continue

        repo_path = ROOT_DIR / repo["path"]
        if repo_path.exists() and (repo_path / ".git").exists():
            print(f"Submodule '{repo['id']}' already initialized at {repo['path']}.")
            continue

        print(f"Initializing submodule for '{repo['id']}'...")
        # Check if already in .gitmodules
        gitmodules = ROOT_DIR / ".gitmodules"
        has_submod = False
        if gitmodules.exists():
            has_submod = repo["path"] in gitmodules.read_text(encoding="utf-8")

        if has_submod:
            run_cmd(["git", "submodule", "update", "--init", "--recursive", repo["path"]], check=True)
        else:
            url = repo["url"]
            print(f"Adding submodule {repo['path']} from {url}...")
            run_cmd(["git", "submodule", "add", url, repo["path"]], check=True)

        print(f"Successfully initialized '{repo['id']}'.")

def cmd_sync_scripts(args: argparse.Namespace) -> None:
    config = load_config()
    source_scripts_dir = ROOT_DIR / "mps-gradle-scripts" / "gradle"
    if not source_scripts_dir.exists():
        print("Error: mps-gradle-scripts submodule is not initialized.", file=sys.stderr)
        sys.exit(1)

    target = args.repo.lower() if args.repo else "all"
    scripts_to_copy = ["download-mps.gradle", "run-mps-ant.gradle", "init-gradle-scripts.gradle"]

    for repo in config["repos"]:
        if repo["id"] == "mps-gradle-scripts":
            continue
        if target != "all" and repo["id"].lower() != target and repo["path"].lower() != target:
            continue

        repo_path = ROOT_DIR / repo["path"]
        if not repo_path.exists():
            print(f"Skipping {repo['id']}: repo path not cloned.")
            continue

        dest_gradle = repo_path / "gradle"
        dest_gradle.mkdir(parents=True, exist_ok=True)

        for s in scripts_to_copy:
            src = source_scripts_dir / s
            dst = dest_gradle / s
            if src.exists():
                shutil.copy2(src, dst)
                print(f"[{repo['id']}] Synced gradle/{s}")

        # Also ensure gradle wrapper is updated if present
        wrapper_props = dest_gradle / "wrapper" / "gradle-wrapper.properties"
        if wrapper_props.exists():
            props_text = wrapper_props.read_text(encoding="utf-8")
            if "gradle-8.2.1" in props_text or "gradle-8.0" in props_text:
                new_props = re.sub(r'gradle-8\.[0-9]+(\.[0-9]+)?-bin\.zip', 'gradle-8.10.2-bin.zip', props_text)
                wrapper_props.write_text(new_props, encoding="utf-8")
                print(f"[{repo['id']}] Upgraded Gradle wrapper to 8.10.2")

        # Ensure gradlew executable bit is set
        gradlew_path = repo_path / "gradlew"
        if gradlew_path.exists():
            try:
                os.chmod(gradlew_path, 0o755)
            except Exception:
                pass

def cmd_migrate(args: argparse.Namespace) -> None:
    config = load_config()
    repo = get_repo_by_id(config, args.repo)
    if not repo:
        print(f"Error: Unknown repo '{args.repo}'", file=sys.stderr)
        sys.exit(1)

    repo_path = ROOT_DIR / repo["path"]
    if not repo_path.exists():
        print(f"Repo {repo['id']} is not cloned yet. Run './orchestrate init {repo['id']}' first.")
        sys.exit(1)

    target_mps = config["targetMpsVersion"]
    print(f"Migrating '{repo['id']}' to MPS {target_mps}...")

    # Step 1: Sync gradle scripts from mps-gradle-scripts
    print("1. Synchronizing gradle scripts...")
    sync_args = argparse.Namespace(repo=repo["id"])
    cmd_sync_scripts(sync_args)

    # Step 2: Update build.gradle ext.mpsVersion
    print(f"2. Updating build.gradle to MPS {target_mps}...")
    build_gradle = repo_path / "build.gradle"
    if build_gradle.exists():
        content = build_gradle.read_text(encoding="utf-8")
        new_content = re.sub(r'ext\.mpsVersion\s*=\s*["\'][^"\']+["\']', f'ext.mpsVersion = "{target_mps}"', content)
        if new_content != content:
            build_gradle.write_text(new_content, encoding="utf-8")
            print(f"[{repo['id']}] Updated ext.mpsVersion to {target_mps}")
        else:
            print(f"[{repo['id']}] ext.mpsVersion is already {target_mps}")
    else:
        print(f"[{repo['id']}] Warning: build.gradle not found.")

    # Step 3: Check build script idea-version
    print("3. Checking build script IDEA range...")
    target_since = config.get("targetIdeaSinceBuild", "261")
    target_until = config.get("targetIdeaUntilBuild", "261.*")
    idea_tag = f'<idea-version since-build="{target_since}" until-build="{target_until}"></idea-version>'
    print(f"   Target IDEA Range: {idea_tag}")

    print("\nMigration preparation complete for " + repo["id"])
    print(f"Next steps for agent/user:")
    print(f"  1. Run: ./orchestrate prepare {repo['id']}   (downloads MPS {target_mps} bundle)")
    print(f"  2. Run: ./orchestrate open {repo['id']}      (launches MPS to execute migrations & MCP)")
    print(f"  3. Connect MCP client using: ./orchestrate mcp-config {repo['id']}")
    print(f"  4. Run: ./orchestrate build {repo['id']}     (validates build)")
    print(f"  5. Run: ./orchestrate test {repo['id']}      (runs MPS tests)")

def get_local_plugin_args(config: Dict[str, Any], mode: str = "local", local_only: Optional[List[str]] = None) -> List[str]:
    if mode == "remote" and not local_only:
        return []

    args: List[str] = []
    for r in config["repos"]:
        if local_only is not None and r["id"] not in local_only:
            continue
        prop = r.get("pluginProperty")
        artifact_rel = r.get("artifactZip")
        if prop and artifact_rel:
            artifact_path = ROOT_DIR / r["path"] / artifact_rel
            if artifact_path.exists():
                uri = artifact_path.resolve().as_uri()
                args.append(f"-P{prop}={uri}")
    return args

def ensure_shared_mps_bundle(config: Dict[str, Any]) -> Path:
    """
    Ensures a single canonical MPS + JBR distribution is extracted under
    <ROOT_DIR>/.mps-shared/<mpsVersion>/Contents (or mps on Linux/Windows),
    reusing an existing extracted bundle if present, or preparing via mps-gradle-scripts.
    """
    target_mps = config["targetMpsVersion"]
    shared_dir = ROOT_DIR / ".mps-shared" / target_mps
    bundle_subdir = "Contents" if sys.platform == "darwin" else "mps"
    shared_bundle = shared_dir / bundle_subdir

    if shared_bundle.exists() and (shared_bundle / "jbr").exists():
        return shared_bundle

    shared_dir.mkdir(parents=True, exist_ok=True)

    # Check if any submodule already has an extracted bundle we can move into .mps-shared
    for r in config["repos"]:
        candidate = ROOT_DIR / r["path"] / "build" / "mps-bundle" / bundle_subdir
        if candidate.exists() and not candidate.is_symlink() and (candidate / "jbr").exists() and not (candidate / "jbr").is_symlink():
            print(f"[shared-bundle] Moving existing MPS {target_mps} bundle from {r['id']} into {shared_bundle}...")
            shutil.move(str(candidate), str(shared_bundle))
            # Strip any repo-specific -Didea.plugins.path lines from shared bin/*.vmoptions
            bin_dir = shared_bundle / "bin"
            if bin_dir.exists():
                for vmopt in bin_dir.glob("*.vmoptions"):
                    lines = [
                        line for line in vmopt.read_text(encoding="utf-8", errors="ignore").splitlines()
                        if not line.strip().startswith("-Didea.plugins.path=")
                    ]
                    vmopt.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return shared_bundle

    # Otherwise build it once in mps-gradle-scripts and move it
    root_repo = get_repo_by_id(config, "mps-gradle-scripts")
    if not root_repo:
        raise RuntimeError("mps-gradle-scripts not found in repos.json")
    root_repo_path = ROOT_DIR / root_repo["path"]
    print(f"[shared-bundle] Preparing initial MPS {target_mps} bundle in mps-gradle-scripts...")
    subprocess.run(["./gradlew", "prepareMps"], cwd=root_repo_path, check=True)
    candidate = root_repo_path / "build" / "mps-bundle" / bundle_subdir
    shutil.move(str(candidate), str(shared_bundle))
    bin_dir = shared_bundle / "bin"
    if bin_dir.exists():
        for vmopt in bin_dir.glob("*.vmoptions"):
            lines = [
                line for line in vmopt.read_text(encoding="utf-8", errors="ignore").splitlines()
                if not line.strip().startswith("-Didea.plugins.path=")
            ]
            vmopt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return shared_bundle


def provision_repo_mps_bundle(repo: Dict[str, Any], config: Dict[str, Any]) -> None:
    """
    Provisions <repo>/build/mps-bundle and <repo>/build/download using symlinks to
    the shared MPS/JBR installation (.mps-shared/<mpsVersion>) and global Gradle cache,
    while giving each repo its own isolated bin/*.vmoptions and dependencies/ directory.
    """
    shared_bundle = ensure_shared_mps_bundle(config)
    repo_path = ROOT_DIR / repo["path"]
    bundle_subdir = "Contents" if sys.platform == "darwin" else "mps"
    repo_bundle_root = repo_path / "build" / "mps-bundle"
    repo_bundle = repo_bundle_root / bundle_subdir

    # If repo_bundle is an unshared full directory (~2GB), replace it with the lightweight linked layout
    if repo_bundle.exists() and not (repo_bundle / "lib").is_symlink():
        print(f"[{repo['id']}] Replacing duplicate 2GB MPS bundle with shared bundle links...")
        shutil.rmtree(repo_bundle, ignore_errors=True)

    repo_bundle.mkdir(parents=True, exist_ok=True)
    deps_dir = repo_bundle_root / "dependencies"
    deps_dir.mkdir(parents=True, exist_ok=True)

    # Link all entries from shared_bundle except 'bin' and 'system'
    for item in shared_bundle.iterdir():
        if item.name in ("bin", "system"):
            continue
        target_link = repo_bundle / item.name
        if not target_link.exists() and not target_link.is_symlink():
            target_link.symlink_to(item.resolve())

    # Copy 'bin' (~1.1MB) and configure repo-specific -Didea.plugins.path in *.vmoptions
    repo_bin = repo_bundle / "bin"
    if repo_bin.is_symlink():
        repo_bin.unlink()
    if not repo_bin.exists():
        shutil.copytree(shared_bundle / "bin", repo_bin, symlinks=True)
        deps_abs = str(deps_dir.resolve())
        for vmopt in repo_bin.glob("*.vmoptions"):
            lines = [
                line for line in vmopt.read_text(encoding="utf-8", errors="ignore").splitlines()
                if not line.strip().startswith("-Didea.plugins.path=")
            ]
            lines.append(f"-Didea.plugins.path={deps_abs}")
            vmopt.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # On macOS, ensure build/mps-bundle/mps -> Contents symlink exists
    if sys.platform == "darwin":
        mps_link = repo_bundle_root / "mps"
        if not mps_link.exists() and not mps_link.is_symlink():
            mps_link.symlink_to(repo_bundle.resolve())

    # Ensure build/dependencies -> build/mps-bundle/dependencies symlink exists
    legacy_deps = repo_path / "build" / "dependencies"
    if not legacy_deps.exists() and not legacy_deps.is_symlink():
        legacy_deps.symlink_to(deps_dir.resolve())

    # Link MPS zip and JBR tar.gz in build/download from ~/.gradle/caches/mps-downloads so downloadMps/downloadJbr skip
    download_dir = repo_path / "build" / "download"
    download_dir.mkdir(parents=True, exist_ok=True)
    gradle_cache = Path.home() / ".gradle" / "caches" / "mps-downloads"
    mps_zip_name = f"mps-{config['targetMpsVersion']}.zip"
    cached_mps_zip = gradle_cache / "mps" / mps_zip_name
    local_mps_zip = download_dir / mps_zip_name
    if cached_mps_zip.exists():
        if local_mps_zip.exists() and not local_mps_zip.is_symlink():
            local_mps_zip.unlink()
        if not local_mps_zip.exists():
            local_mps_zip.symlink_to(cached_mps_zip.resolve())

    jbr_cache_dir = gradle_cache / "jbr"
    if jbr_cache_dir.exists():
        for jbr_archive in jbr_cache_dir.glob(f"jbr-{config['targetJbrVersion']}*.tar.gz"):
            local_jbr = download_dir / jbr_archive.name
            if local_jbr.exists() and not local_jbr.is_symlink():
                local_jbr.unlink()
            if not local_jbr.exists():
                local_jbr.symlink_to(jbr_archive.resolve())


def run_gradle(repo: Dict[str, Any], config: Dict[str, Any], task: str, mode: str = "local", local_only: Optional[List[str]] = None, extra_args: Optional[List[str]] = None) -> None:
    repo_path = ROOT_DIR / repo["path"]

    # Provision lightweight shared MPS/JBR bundle links before prepareMps or openProjectInMps
    if task in ("prepareMps", "openProjectInMps"):
        provision_repo_mps_bundle(repo, config)

    # When --mode remote is used on prepare, delete download plugins and bundle dependencies
    # so Gradle re-downloads them from remote GitHub release URLs instead of reusing local caches.
    if task == "prepareMps" and mode == "remote":
        plugins_cache = repo_path / "build" / "download" / "plugins"
        bundle_deps = repo_path / "build" / "mps-bundle" / "dependencies"
        if plugins_cache.exists():
            print(f"[{repo['id']}] Clearing {plugins_cache} for remote dependency fetch...")
            shutil.rmtree(plugins_cache, ignore_errors=True)
        if bundle_deps.exists():
            print(f"[{repo['id']}] Clearing {bundle_deps} for remote dependency fetch...")
            shutil.rmtree(bundle_deps, ignore_errors=True)

    plugin_args = get_local_plugin_args(config, mode=mode, local_only=local_only)
    cmd = ["./gradlew", task] + plugin_args
    if extra_args:
        cmd.extend(extra_args)

    print(f"Running '{' '.join(cmd)}' in {repo_path} (mode: {mode})...")
    subprocess.run(cmd, cwd=repo_path, check=True)

def cmd_prepare(args: argparse.Namespace) -> None:
    config = load_config()
    repo = get_repo_by_id(config, args.repo)
    if not repo:
        print(f"Error: Unknown repo '{args.repo}'", file=sys.stderr)
        sys.exit(1)

    run_gradle(repo, config, "prepareMps", mode=args.mode, local_only=args.local_only)

def cmd_build(args: argparse.Namespace) -> None:
    config = load_config()
    repo = get_repo_by_id(config, args.repo)
    if not repo:
        print(f"Error: Unknown repo '{args.repo}'", file=sys.stderr)
        sys.exit(1)

    run_gradle(repo, config, "mpsBuild", mode=args.mode, local_only=args.local_only)

def cmd_test(args: argparse.Namespace) -> None:
    config = load_config()
    repo = get_repo_by_id(config, args.repo)
    if not repo:
        print(f"Error: Unknown repo '{args.repo}'", file=sys.stderr)
        sys.exit(1)

    run_gradle(repo, config, "mpsTest", mode=args.mode, local_only=args.local_only)

def cmd_open(args: argparse.Namespace) -> None:
    config = load_config()
    repo = get_repo_by_id(config, args.repo)
    if not repo:
        print(f"Error: Unknown repo '{args.repo}'", file=sys.stderr)
        sys.exit(1)

    print(f"Opening project '{repo['id']}' in MPS 2026.1 (mode: {args.mode})...")
    run_gradle(repo, config, "openProjectInMps", mode=args.mode, local_only=args.local_only)

def cmd_share_bundles(args: argparse.Namespace) -> None:
    config = load_config()
    target = args.repo.lower() if args.repo else "all"
    ensure_shared_mps_bundle(config)

    for repo in config["repos"]:
        if target != "all" and repo["id"].lower() != target and repo["path"].lower() != target:
            continue
        repo_path = ROOT_DIR / repo["path"]
        if not repo_path.exists():
            continue
        provision_repo_mps_bundle(repo, config)
    print("Shared MPS/JBR bundle linked across target repositories.")


def cmd_mcp_config(args: argparse.Namespace) -> None:
    repo_id = args.repo or "mps-gradle-scripts"
    print("=" * 70)
    print(" Model Context Protocol (MCP) Configuration for MPS 2026.1")
    print("=" * 70)
    print("MPS 2026.1 embeds native MCP support via the Projectional Agent Toolkit")
    print("(`jetbrains.mps.agents.mcp.tools` / `com.intellij.mcpServer`).")
    print("")
    print("1. Ensure MPS is launched with your target project:")
    print(f"   ./orchestrate open {repo_id}")
    print("")
    print("2. Ensure MCP Server is enabled in MPS (Settings -> Tools -> MCP Server).")
    print("   Default IDE port is 63342.")
    print("")
    print("3. Client Configuration for AI Agents (Antigravity / Claude Code / etc.):")
    print("-" * 70)
    mcp_config = {
        "mcpServers": {
            "mps-2026": {
                "command": "npx",
                "args": ["-y", "@jetbrains/mcp-proxy"],
                "env": {
                    "IDE_PORT": "63342"
                }
            }
        }
    }
    print(json.dumps(mcp_config, indent=2))
    print("-" * 70)
    print("Projectional MCP tools available once connected:")
    print("  * get_modules / get_models / get_nodes")
    print("  * run_migrations: Executes all pending MPS migrations")
    print("  * make_model / make_solution / rebuild_project")
    print("  * query_references / resolve_concept")
    print("=" * 70)

def main() -> None:
    parser = argparse.ArgumentParser(description="ViMoTest MPS Hybrid Orchestration Tool")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # status
    p_status = subparsers.add_parser("status", help="Show migration status across all repos")

    # next
    p_next = subparsers.add_parser("next", help="Find the next repository to migrate in dependency order")

    # init
    p_init = subparsers.add_parser("init", help="Initialize git submodules")
    p_init.add_argument("repo", nargs="?", default="all", help="Repository ID or 'all'")

    # sync-scripts
    p_sync = subparsers.add_parser("sync-scripts", help="Synchronize gradle scripts from mps-gradle-scripts")
    p_sync.add_argument("repo", nargs="?", default="all", help="Target repository ID or 'all'")

    # migrate
    p_mig = subparsers.add_parser("migrate", help="Run automated migration steps for a repo")
    p_mig.add_argument("repo", help="Target repository ID")

    def add_mode_arguments(p: argparse.ArgumentParser) -> None:
        p.add_argument("--mode", choices=["local", "remote"], default="local", help="Dependency resolution mode (default: local)")
        p.add_argument("--local-only", nargs="*", default=None, help="Repositories to keep local even in remote mode or selective local mode")

    # prepare
    p_prep = subparsers.add_parser("prepare", help="Download and prepare MPS bundle")
    p_prep.add_argument("repo", help="Target repository ID")
    add_mode_arguments(p_prep)

    # build
    p_build = subparsers.add_parser("build", help="Run MPS ant build")
    p_build.add_argument("repo", help="Target repository ID")
    add_mode_arguments(p_build)

    # test
    p_test = subparsers.add_parser("test", help="Run MPS ant tests")
    p_test.add_argument("repo", help="Target repository ID")
    add_mode_arguments(p_test)

    # open
    p_open = subparsers.add_parser("open", help="Open project in MPS")
    p_open.add_argument("repo", help="Target repository ID")
    add_mode_arguments(p_open)

    # share-bundles
    p_share = subparsers.add_parser("share-bundles", help="Deduplicate MPS/JBR bundles across submodules using .mps-shared symlinks")
    p_share.add_argument("repo", nargs="?", default="all", help="Repository ID or 'all'")

    # mcp-config
    p_mcp = subparsers.add_parser("mcp-config", help="Show MCP configuration for MPS 2026.1")
    p_mcp.add_argument("repo", nargs="?", default="", help="Repository ID")

    args = parser.parse_args()

    if not args.command or args.command == "status":
        cmd_status(args)
    elif args.command == "next":
        cmd_next(args)
    elif args.command == "init":
        cmd_init(args)
    elif args.command == "sync-scripts":
        cmd_sync_scripts(args)
    elif args.command == "migrate":
        cmd_migrate(args)
    elif args.command == "prepare":
        cmd_prepare(args)
    elif args.command == "build":
        cmd_build(args)
    elif args.command == "test":
        cmd_test(args)
    elif args.command == "open":
        cmd_open(args)
    elif args.command == "share-bundles":
        cmd_share_bundles(args)
    elif args.command == "mcp-config":
        cmd_mcp_config(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()

