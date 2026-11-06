This repo orchestrates the single isolated MPS repositories for ViMoTest.

## Process

foreach repo:
* perform downloadGradleScripts
* MPS to target version in build.gradle, and dependencies
* use MCP to start MPS
* MPS Migrationen all processed
* Check Build script
    * Version update
    * IDEA Range
    `<idea-version since-build="261" until-build="261.*"></idea-version>`

=> Migrate to MPS 2026.1

## Tracer Bullet

start with https://github.com/vimotest/mps-gradle-scripts



## Repos

(last to first).

mps-vimotest-samples (last)




mps-vimotest




mps-alfi-samples




mps-alfi




CppBaseLanguage




CsBaseLanguage




Editor2PDF




TextGenGen Fum




mps-requirements-dsl




Gradle Setup Sample




mps-gradle-scripts (first)
