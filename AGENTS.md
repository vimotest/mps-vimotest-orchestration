# AI Agent Guide: ViMoTest MPS 2026.1 Migration Orchestration

This repository provides a **hybrid orchestration layer** for migrating decentralized JetBrains MPS repositories to **MPS 2026.1** using Git submodules and native **Model Context Protocol (MCP)** support.

---

## 1. Architecture Overview

- **Decentralized Independence**: Each repository retains its own Git history, CI/CD workflows, release tags, and issue tracking.
- **Hybrid Submodule Layer**: Submodules are organized in dependency order inside this orchestration repo (`repos.json`).
- **Tracer Bullet Completed**: `mps-gradle-scripts` serves as the root tooling layer. It defines JBR 25 mappings (`25.0.3-b329.124`), Gradle 8.10+, and MPS 2026.1 download & ANT tasks.
- **Native MCP Interaction**: JetBrains MPS 2026.1 bundles the **Projectional Agent Toolkit** (`jetbrains.mps.agents.mcp.tools` built on `com.intellij.mcpServer`), enabling agents to query models, execute migrations, verify constraints, and build solutions programmatically.

---

## 2. Migration Order (Dependency Chain)

Migrations must be performed strictly in dependency order:

| # | Repository | Type | Dependencies | Key Role |
|---|------------|------|--------------|----------|
| 1 | `mps-gradle-scripts` | Tooling | *None* | Root gradle scripts provider |
| 2 | `mps-gradle-setup-sample` | Sample | `mps-gradle-scripts` | Validation sample |
| 3 | `vimotest-requirements-dsl`| Language | `mps-gradle-scripts` | Requirements DSL |
| 4 | `textGenGen-fum` | Tooling | `mps-gradle-scripts` | TextGen generation |
| 5 | `Editor2PDF` | Utility | `mps-gradle-scripts` | Editor PDF export |
| 6 | `CsBaseLanguage` | Language | `mps-gradle-scripts` | C# MPS BaseLanguage |
| 7 | `CppBaseLanguage` | Language | `mps-gradle-scripts` | C++ MPS BaseLanguage |
| 8 | `mps-alfi` | Language | `mps-gradle-scripts`, `CsBaseLanguage`, `CppBaseLanguage` | Action Language for UML |
| 9 | `mps-alfi-samples` | Sample | `mps-alfi` | ALFI samples & tests |
| 10 | `mps-vimotest` | Language | `mps-gradle-scripts`, `vimotest-requirements-dsl`, `Editor2PDF`, `mps-alfi` | Core ViMoTest framework |
| 11 | `mps-vimotest-samples` | Sample | `mps-vimotest` | ViMoTest end-to-end tests |

---

## 3. The Migration Workflow per Repository

For each repository in the chain:

### Step 1: Initialize Submodule
```bash
./orchestrate init <repo-id>
```

### Step 2: Automated Preparation
```bash
./orchestrate migrate <repo-id>
```
This automatically:
- Syncs updated `download-mps.gradle`, `run-mps-ant.gradle`, and `init-gradle-scripts.gradle` from `mps-gradle-scripts`.
- Updates `ext.mpsVersion = "2026.1"` in `build.gradle`.
- Upgrades Gradle wrapper to 8.10.2 (supporting modern JDKs).

### Step 3: Prepare MPS Distribution
```bash
./orchestrate prepare <repo-id>
```
Downloads MPS 2026.1, JBR 25, and configured plugins into `build/mps-bundle`.

### Step 4: Open Project in MPS & Run Migrations via MCP
Launch MPS:
```bash
./orchestrate open <repo-id>
```
Connect your MCP client to the running instance (port 63342) using `@jetbrains/mcp-proxy`.
Available MCP actions:
- `run_migrations`: Execute all pending MPS version migrations.
- `make_model` / `make_solution`: Rebuild models.
- Inspect AST nodes and fix migration issues safely without raw XML edits.

### Step 5: Check Build Script & IDEA Range
In MPS build solution or generated XML:
- Ensure IDEA platform range matches MPS 2026.1 (build `261`):
  ```xml
  <idea-version since-build="261" until-build="261.*"></idea-version>
  ```
- Build the build model: *Make Solution*

### Step 6: Validate Build & Tests
```bash
./orchestrate build <repo-id>
./orchestrate test <repo-id>
```

### Step 7: Commit, Tag & Release
Commit the changes in the submodule repository, create the release tag, and push. Then update the submodule pointer in this orchestration repo.

```bash
cd <repo-id>
git add -A
git commit -m "Migrate to MPS 2026.1"
git tag -a 2026.1.0 -m "Release 2026.1.0"
# git push && git push --tags
cd ..
git add <repo-id>
git commit -m "Update <repo-id> submodule pointer to MPS 2026.1"
```

### Step 8: Proceed to Next Repository
```bash
./orchestrate next
```

---

## 4. MCP Agent Configuration

To connect Antigravity or any MCP agent to the running MPS instance:

```json
{
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
```

Verify status anytime using:
```bash
./orchestrate status
```

