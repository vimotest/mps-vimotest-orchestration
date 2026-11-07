# ViMoTest MPS Migration Orchestration

A **hybrid orchestration layer** for migrating the 11 decentralized JetBrains MPS repositories in the ViMoTest ecosystem to **MPS 2026.1** (JBR `25.0.3-b329.124`, Gradle `8.10.2`).

Each repository retains its own Git history, CI/CD workflows, and GitHub Releases, while this orchestration workspace provides:
1. **Strict Topological Ordering**: Submodules managed via [`repos.json`](repos.json).
2. **Dual-Mode Dependency Resolution**: Seamless switching between local sibling artifacts (`--mode local`) and published GitHub Release assets (`--mode remote`).
3. **Zero-Duplication Shared MPS Bundle**: A single `.mps-shared/2026.1` distribution symlinked across all submodules (~22 GB disk space saved).
4. **Native MCP Agent Integration**: Direct integration with the MPS 2026.1 **Projectional Agent Toolkit** (`jetbrains.mps.agents.mcp.tools`).

---

## Quick Start (`./orchestrate`)

```bash
# 1. Inspect status across all 11 repositories
./orchestrate status

# 2. Identify the next repository ready for migration
./orchestrate next

# 3. Initialize submodules and deduplicate MPS/JBR bundles
./orchestrate init all
./orchestrate share-bundles

# 4. Fully automated headless migration (scripts, bundle, models, build & tests)
./orchestrate migrate <repo-id> --build --test

# 5. Build and test individually (Local Sibling Mode - default)
./orchestrate build <repo-id>
./orchestrate test <repo-id>

# 6. Verify against published GitHub Releases (Remote CI Mode)
./orchestrate prepare <repo-id> --mode remote
./orchestrate build <repo-id> --mode remote
./orchestrate test <repo-id> --mode remote

# 7. Launch MPS 2026.1 GUI & inspect MCP configuration
./orchestrate open <repo-id>
./orchestrate mcp-config <repo-id>
```

---

## Repository Dependency Chain & Rollout Status (MPS 2026.1)

Migrations and releases must proceed strictly in topological order (1 to 11):

| # | Repository | Type | Upstream Dependencies | Artifact / Plugin Property | MPS 2026.1 Release |
|:-:|---|---|---|---|---|
| 1 | [`mps-gradle-scripts`](mps-gradle-scripts) | Tooling | *None* | Root Gradle scripts | `2026.1.0` |
| 2 | [`mps-gradle-setup-sample`](mps-gradle-setup-sample) | Sample | 1 | Validation sample (1/1 tests) | `2026.1.0` |
| 3 | [`vimotest-requirements-dsl`](vimotest-requirements-dsl) | Language | 1 | Requirements DSL | `2026.1.0` |
| 4 | [`textGenGen-fum`](textGenGen-fum) | Tooling | 1 | `TextGenGen.zip` (`textGenGenPluginUrl`) | `2026.1.0` |
| 5 | [`Editor2PDF`](Editor2PDF) | Utility | 1 | Editor PDF export plugin | `2026.1.0` |
| 6 | [`CsBaseLanguage`](CsBaseLanguage) | Language | 1, 4 | `CsBaseLanguage.zip` (`csBaseLanguagePluginUrl`) | `2026.1.0` |
| 7 | [`CppBaseLanguage`](CppBaseLanguage) | Language | 1, 4 | `CppBaseLanguage.zip` (`cppBaseLanguagePluginUrl`) | `2026.1.0` |
| 8 | [`mps-alfi`](mps-alfi) | Language | 1, 4, 6, 7 | `alfi.zip` (`alfiPluginUrl`) | `2026.1.0` |
| 9 | [`mps-alfi-samples`](mps-alfi-samples) | Sample | 8, 6, 7 | ALFI end-to-end samples | `2026.1.0` |
| 10 | [`mps-vimotest`](mps-vimotest) | Language | 1, 3, 5, 8, 6, 7 | `mps-vimotest.zip` (`vimotestPluginUrl`) | `2026.1.0` |
| 11 | [`mps-vimotest-samples`](mps-vimotest-samples) | Sample | 10, 8, 6, 7 | ViMoTest end-to-end samples (13/13 tests) | `2026.1.0` |

---

## Documentation

Detailed guides are located in [`docs/`](docs/):

- **[Architecture & Hybrid Layer Design](docs/ARCHITECTURE.md)**: Decentralized repo design, dual-mode dependency resolution (`local` vs `remote`), and `.mps-shared` bundle deduplication.
- **[Migration Playbook](docs/MIGRATION_PLAYBOOK.md)**: End-to-end checklist for migrating, testing, tagging, and publishing clean GitHub Releases.
- **[Model Context Protocol (MCP) Integration](docs/MCP_AGENT_INTEGRATION.md)**: Connecting AI coding agents to the live MPS 2026.1 instance on port `63342`.
- **[Troubleshooting & Known Pitfalls](docs/TROUBLESHOOTING.md)**: Verified fixes for IntelliJ 261 modular JAR classpaths, JDK 21 vs JDK 25 bytecode execution in `compitest`, IDEA version ranges, and tag conventions.
- **[AI Agent Operational Guide](AGENTS.md)**: Concise instructions and rules for autonomous coding agents.
