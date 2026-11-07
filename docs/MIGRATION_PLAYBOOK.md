# ViMoTest MPS Migration Playbook

This playbook outlines the exact step-by-step process for executing migrations to target MPS versions across all repositories.

---

## 1. Prerequisites

- **Python 3.10+**: Drives the `./orchestrate` CLI.
- **Git 2.30+**: Manages decentralized submodules.
- **Node.js 18+ (Optional)**: Required only when launching the MCP client proxy (`@jetbrains/mcp-proxy`).
- **Target Platform Metadata**: Defined centrally in [`repos.json`](../repos.json):
  - `targetMpsVersion`: e.g. `"2026.1"`
  - `targetIdeaSinceBuild`: e.g. `"261"`
  - `targetIdeaUntilBuild`: e.g. `"261.*"`
  - `targetJbrVersion`: e.g. `"25.0.3-b329.124"`

---

## 2. Step-by-Step Workflow per Repository

Repositories must be migrated strictly in topological dependency order (1 to 11).

### Step 1: Initialize the Submodule
```bash
./orchestrate init <repo-id>
```
*Clones or updates the submodule into the workspace if not already present.*

### Step 2: Automated Preparation
```bash
./orchestrate migrate <repo-id>
```
This automatically performs three actions:
1. Syncs `download-mps.gradle`, `run-mps-ant.gradle`, and `init-gradle-scripts.gradle` from `mps-gradle-scripts`.
2. Updates `ext.mpsVersion = "<target-version>"` in the repository's `build.gradle`.
3. Upgrades `gradle-wrapper.properties` to Gradle 8.10.2+ (for Java 21 / 25 support).

### Step 3: Prepare the MPS Distribution Bundle
```bash
./orchestrate prepare <repo-id>
```
Downloads and unpacks:
- MPS distribution bundle into `build/mps-bundle/mps`.
- JBR distribution into `build/mps-bundle/jbr`.
- All required plugins (from sibling builds or remote releases) into `build/mps-bundle/dependencies`.

### Step 4: Run Model Migrations (Headless or MCP)

#### Option A: Headless ANT Generation
```bash
./orchestrate build <repo-id>
```
If the project's models are already compatible or trivial, running the ANT generator directly will update generated files.

#### Option B: Interactive Migration via Model Context Protocol (MCP)
For non-trivial migrations (language version bumps, deprecated concept migrations, structural repairs):
1. Open the project in the target MPS version:
   ```bash
   ./orchestrate open <repo-id>
   ```
2. In MPS, ensure MCP Server is enabled under **Settings -> Tools -> MCP Server** (default IDE port `63342`).
3. Connect an AI agent using `@jetbrains/mcp-proxy`:
   ```bash
   ./orchestrate mcp-config <repo-id>
   ```
4. Instruct the agent to run version migrations and fix AST discrepancies.

### Step 5: Check Build Script & IDEA Version Range
Inspect the repository's MPS build script or generated `build.xml`:
1. **IntelliJ Classpath**: Ensure javac classpath contains the full platform JAR fileset rather than fragile individual JAR lists:
   ```xml
   <fileset dir="${artifacts.mps}/lib" includes="*.jar" />
   ```
2. **IDEA Version Compatibility**: If the repository distributes an IntelliJ/MPS plugin, update the `<idea-version>` range in the build model or `build.xml`:
   ```xml
   <idea-version since-build="261" until-build="261.*"></idea-version>
   ```

### Step 6: Validate Build & Tests (Local & Remote Modes)
First validate using local sibling artifacts (`--mode local`, default):
```bash
./orchestrate build <repo-id>
./orchestrate test <repo-id>
```
Once upstream dependencies are published to GitHub Releases, verify decentralized resolution in `--mode remote`:
```bash
./orchestrate prepare <repo-id> --mode remote
./orchestrate build <repo-id> --mode remote
./orchestrate test <repo-id> --mode remote
```

### Step 7: Commit, Tag, Publish Clean GitHub Release & Update Submodule Pointer

> [!IMPORTANT]
> **Release Conventions**:
> 1. **Bare Semantic Tags Only**: Always use `2026.1.0` (**never** `v2026.1.0`).
> 2. **Dual Remote for `mps-alfi`**: Push `mps-alfi` to both `origin` (`Fumapps/mps-alfi-rework`) and `vimotest` (`vimotest/mps-alfi`) so downstream URLs pointing to `vimotest/mps-alfi` resolve.
> 3. **Clean Release Notes**: The CI `github-actions-release.yaml` workflow creates a draft prerelease containing `TODO: write changes...` placeholders. Always publish the release and overwrite the body with clean notes.

Execute inside the submodule:
```bash
cd <repo-id>
git add -A
git commit -m "Migrate to MPS 2026.1"
git tag -a 2026.1.0 -m "Release 2026.1.0"
git push origin HEAD && git push origin 2026.1.0
cd ..
```

After the GitHub Actions `Release Build` workflow completes, publish the release and clean up its release notes:
```bash
gh release edit 2026.1.0 -R <owner>/<repo> \
  --draft=false --prerelease=false --latest \
  --title "Release 2026.1.0" \
  --notes "Release 2026.1.0 for JetBrains MPS 2026.1."
```

Then update the submodule pointer in the orchestration repository:
```bash
git add <repo-id>
git commit -m "Update <repo-id> submodule pointer to MPS 2026.1"
```

### Step 8: Advance to Next Repository
```bash
./orchestrate next
```
Repeat Steps 1–7 for the remaining repositories down the chain.

