# ViMoTest MPS Migration Orchestration

This repository orchestrates the single isolated JetBrains MPS repositories for the ViMoTest ecosystem into a **hybrid layer**. Submodules allow each repository to remain decentralized, while enabling AI agents to drive the migration step-by-step through the dependency chain to **MPS 2026.1** via the **Model Context Protocol (MCP)**.

---

## Process

For each repository in the chain:
1. **Initialize submodule**: Clones the decentralized repo locally.
2. **Synchronize Gradle scripts**: Pulls latest `download-mps.gradle`, `run-mps-ant.gradle`, and `init-gradle-scripts.gradle`.
3. **Configure MPS target version**: Sets `ext.mpsVersion = "2026.1"` and updates plugin dependencies in `build.gradle`.
4. **Prepare MPS distribution**: Downloads MPS 2026.1 and JBR 25 via `./gradlew prepareMps`.
5. **Launch MPS & Run Migrations via MCP**:
   - Opens MPS via `./gradlew openProjectInMps`.
   - Connects AI agents to MPS embedded MCP server (`jetbrains.mps.agents.mcp.tools` / `com.intellij.mcpServer`).
   - Executes pending migrations structurally without raw XML corruption.
6. **Check Build Script**:
   - Update version.
   - Set IDEA build compatibility range:
     ```xml
     <idea-version since-build="261" until-build="261.*"></idea-version>
     ```
7. **Verify & Release**:
   - Run `./gradlew mpsBuild` and `./gradlew mpsTest`.
   - Commit, tag release, and push upstream.
   - Update submodule pointer in this orchestration repo.
   - Advance down the dependency chain to the next repository.

---

## Orchestrator CLI (`./orchestrate`)

The included `./orchestrate` CLI automates status tracking, script synchronization, and migration commands:

```bash
# Check status across all 11 repositories
./orchestrate status

# Find the next repository ready for migration
./orchestrate next

# Initialize a specific submodule (or 'all')
./orchestrate init mps-gradle-setup-sample

# Run automated migration prep (sync scripts + bump build.gradle)
./orchestrate migrate mps-gradle-setup-sample

# Download & bundle MPS 2026.1 for a repo
./orchestrate prepare mps-gradle-setup-sample

# Open project in MPS 2026.1
./orchestrate open mps-gradle-setup-sample

# Display MCP server configuration for AI agents
./orchestrate mcp-config

# Validate MPS build and test suite
./orchestrate build mps-gradle-setup-sample
./orchestrate test mps-gradle-setup-sample
```

---

## Tracer Bullet: `mps-gradle-scripts` (Completed)

The tracer bullet proves that migrating the foundation to MPS 2026.1 is technically viable:
* **JBR 25 Mapping**: Added `"2026.1": "25.0.3-b329.124"` to `gradle/download-mps.gradle`.
* **Verified JetBrains URLs**: Verified availability of MPS 2026.1 zip and JBR 25 tarball on JetBrains CDN.
* **Gradle Wrapper**: Upgraded wrapper to `8.10.2` to support modern JDKs (JDK 21, 23, 25).
* **Validation**: Executed `./gradlew tasks --group=mps-download` and `./gradlew listPlugins` successfully for MPS 2026.1.
* **Committed**: Changes committed to `mps-gradle-scripts` submodule and tracked in this repo.

---

## Repos (Dependency Order: First to Last)

| # | Repository | Submodule Path | Dependencies | Upstream URL |
|---|------------|----------------|--------------|--------------|
| 1 | **mps-gradle-scripts** (first) | `mps-gradle-scripts` | *None* | https://github.com/vimotest/mps-gradle-scripts |
| 2 | **Gradle Setup Sample** | `mps-gradle-setup-sample` | `mps-gradle-scripts` | https://github.com/Fumapps/mps-gradle-setup-sample |
| 3 | **mps-requirements-dsl** | `vimotest-requirements-dsl` | `mps-gradle-scripts` | https://github.com/vimotest/vimotest-requirements-dsl |
| 4 | **TextGenGen Fum** | `textGenGen-fum` | `mps-gradle-scripts` | https://github.com/Fumapps/textGenGen-fum |
| 5 | **Editor2PDF** | `Editor2PDF` | `mps-gradle-scripts` | https://github.com/Fumapps/Editor2PDF |
| 6 | **CsBaseLanguage** | `CsBaseLanguage` | `mps-gradle-scripts` | https://github.com/Fumapps/CsBaseLanguage |
| 7 | **CppBaseLanguage** | `CppBaseLanguage` | `mps-gradle-scripts` | https://github.com/Fumapps/CppBaseLanguage |
| 8 | **mps-alfi** | `mps-alfi` | `CsBaseLanguage`, `CppBaseLanguage` | https://github.com/Fumapps/mps-alfi-rework |
| 9 | **mps-alfi-samples** | `mps-alfi-samples` | `mps-alfi` | https://github.com/vimotest/mps-alfi-samples |
| 10 | **mps-vimotest** | `mps-vimotest` | `vimotest-requirements-dsl`, `Editor2PDF`, `mps-alfi` | https://github.com/vimotest/mps-vimotest |
| 11 | **mps-vimotest-samples** (last) | `mps-vimotest-samples` | `mps-vimotest` | https://github.com/vimotest/mps-vimotest-samples |

See [AGENTS.md](AGENTS.md) for detailed AI agent operational instructions.
