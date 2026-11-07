# AI Agent Guide: ViMoTest MPS 2026.1 Migration Orchestration

This repository provides a **hybrid orchestration layer** for migrating decentralized JetBrains MPS repositories to **MPS 2026.1** using Git submodules, shared MPS/JBR bundles, dual-mode dependency resolution, and native **Model Context Protocol (MCP)** support.

---

## 1. Core Principles

- **Decentralized Independence**: Each submodule retains its own Git repository, CI/CD workflows, and GitHub Releases. Never hardcode relative sibling paths (`../`) inside a submodule's `build.gradle`.
- **Dual-Mode Dependency Resolution**:
  - `--mode local` (default): `./orchestrate` injects `-P<pluginProperty>=file:///...` for locally built sibling artifacts defined in [`repos.json`](repos.json).
  - `--mode remote`: `./orchestrate` clears cached plugins and tests the exact fallback GitHub Release URLs (`https://github.com/.../releases/download/2026.1.0/*.zip`) used by standalone CI.
- **Shared MPS/JBR Bundle (`.mps-shared/`)**: `./orchestrate` maintains a single canonical MPS + JBR installation in `.mps-shared/<mpsVersion>` and provisions lightweight symlinks into each submodule's `build/mps-bundle` while keeping `bin/*.vmoptions` and `dependencies/` isolated per repository.
- **Native MCP Interaction**: MPS 2026.1 bundles the **Projectional Agent Toolkit** (`jetbrains.mps.agents.mcp.tools`), allowing structural AST queries, model migrations, and builds without raw XML corruption.

---

## 2. Topological Migration Order

Migrations and releases must proceed strictly in dependency order:

| # | Repository | Type | Dependencies | Plugin Property (`repos.json`) |
|:-:|---|---|---|---|
| 1 | `mps-gradle-scripts` | Tooling | *None* | *None* |
| 2 | `mps-gradle-setup-sample` | Sample | `mps-gradle-scripts` | *None* |
| 3 | `vimotest-requirements-dsl` | Language | `mps-gradle-scripts` | *None* |
| 4 | `textGenGen-fum` | Tooling | `mps-gradle-scripts` | `textGenGenPluginUrl` |
| 5 | `Editor2PDF` | Utility | `mps-gradle-scripts` | *None* |
| 6 | `CsBaseLanguage` | Language | `mps-gradle-scripts`, `textGenGen-fum` | `csBaseLanguagePluginUrl` |
| 7 | `CppBaseLanguage` | Language | `mps-gradle-scripts`, `textGenGen-fum` | `cppBaseLanguagePluginUrl` |
| 8 | `mps-alfi` | Language | `mps-gradle-scripts`, `textGenGen-fum`, `CsBaseLanguage`, `CppBaseLanguage` | `alfiPluginUrl` |
| 9 | `mps-alfi-samples` | Sample | `mps-alfi`, `CsBaseLanguage`, `CppBaseLanguage` | *None* |
| 10 | `mps-vimotest` | Language | `mps-gradle-scripts`, `vimotest-requirements-dsl`, `Editor2PDF`, `mps-alfi`, `CsBaseLanguage`, `CppBaseLanguage` | `vimotestPluginUrl` |
| 11 | `mps-vimotest-samples` | Sample | `mps-vimotest`, `mps-alfi`, `CsBaseLanguage`, `CppBaseLanguage` | *None* |

---

## 3. Standard Migration & Release Workflow per Repository

### Step 1: Automated Headless Migration, Build & Test
```bash
./orchestrate init <repo-id>
./orchestrate migrate <repo-id> --build --test
```
This single command automates the entire migration pipeline:
1. Syncs `download-mps.gradle`, `run-mps-ant.gradle`, and `init-gradle-scripts.gradle` from `mps-gradle-scripts`.
2. Updates `ext.mpsVersion = "2026.1"` in `build.gradle` and upgrades Gradle wrapper to `8.10.2`.
3. Provisions the shared `.mps-shared/2026.1` bundle and unpacks dependencies into `build/mps-bundle/dependencies`.
4. Executes headless model migration (`mpsAntMigrate` via `jetbrains.mps.build.ant.MigrationTask`), applying all version migration scripts and bumping `.mps/migration.xml` to `project.migrated.version = "261"`.
5. Compiles (`mpsBuild`) and runs test suites (`mpsTest`) in a clean environment with isolated testbench caches.

### Step 2: Verification of Migration Markers
Ensure `.mps/migration.xml` documents the migrated version:
```bash
grep "project.migrated.version" <repo-id>/.mps/migration.xml
# Expected output: <entry key="project.migrated.version" value="261" />
```
*(Optional GUI inspection: `./orchestrate open <repo-id>` exports `MPS_VM_OPTIONS` automatically so plugins load without deployment errors).*

### Step 3: Validate Standalone Resolution (`--mode remote`)
Once upstream dependencies are released on GitHub, verify fallback resolution:
```bash
./orchestrate prepare <repo-id> --mode remote
./orchestrate build <repo-id> --mode remote
./orchestrate test <repo-id> --mode remote
```

### Step 4: Tag, Push & Clean Up GitHub Release Notes
> **Important Rules**:
> 1. **No `v` prefix on tags**: Always tag as `2026.1.0` (never `v2026.1.0`).
> 2. **`mps-alfi` dual remote**: Push `mps-alfi` to both `origin` (`Fumapps/mps-alfi-rework`) and `vimotest` (`vimotest/mps-alfi`) so downstream URLs `https://github.com/vimotest/mps-alfi/releases/download/...` resolve.
> 3. **Clean Release Notes**: The automated `github-actions-release.yaml` workflow creates a draft prerelease containing placeholder `TODO: write changes...` lines. Always publish the release and replace the placeholder body with concise release notes:

```bash
gh release edit 2026.1.0 -R <owner>/<repo> \
  --draft=false --prerelease=false --latest \
  --title "Release 2026.1.0" \
  --notes "Release 2026.1.0 for JetBrains MPS 2026.1."
```

### Step 5: Update Orchestration Submodule Pointer
```bash
git add <repo-id>
git commit -m "Update <repo-id> submodule pointer to MPS 2026.1"
```
