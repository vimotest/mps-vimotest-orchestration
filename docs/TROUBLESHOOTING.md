# Troubleshooting & Known Pitfalls: MPS 2026.1 Migration

This document captures all technical pitfalls, root causes, and verified solutions encountered during the migration of the 11 ViMoTest repositories to **MPS 2026.1**.

---

## 1. Classpath Compilation Errors (`PossiblyDumbAware` Missing)

### Symptom
When running `mpsBuild` or `java.compile.*`, `javac` fails with errors such as:
```
[javac] Klassendatei für com.intellij.openapi.project.PossiblyDumbAware nicht gefunden
[javac] class file for com.intellij.openapi.project.PossiblyDumbAware not found
```

### Root Cause
In MPS 2025.x and earlier, build scripts often listed individual JAR files explicitly:
```xml
<fileset file="${artifacts.mps}/lib/mps-core.jar" />
<fileset file="${artifacts.mps}/lib/app.jar" />
<fileset file="${artifacts.mps}/lib/lib.jar" />
```
In MPS 2026.1 (IntelliJ platform build 261), many core platform classes were relocated across new modularized JARs (e.g. `intellij.*.jar`, `app-backend.jar`, etc.). When a class references an interface located in an unlisted JAR, `javac` fails.

### Solution
In the repository's `build.xml` (or build script model), add the entire `${artifacts.mps}/lib` directory to the javac classpath:
```xml
<fileset dir="${artifacts.mps}/lib" includes="*.jar" />
```
This ensures all transitive IntelliJ platform classes are available during compilation.

---

## 2. Legacy `build/dependencies` Path Mismatch

### Symptom
Ant build fails during `fetchDependencies` or `generate` stating that dependency plugins cannot be found under `${basedir}/build/dependencies`.

### Root Cause
Older Ant build scripts used:
```xml
<property name="dependencies_home" location="${basedir}/build/dependencies" />
```
However, modern Gradle scripts from `mps-gradle-scripts` download and extract bundles into:
```
${basedir}/build/mps-bundle/dependencies
```

### Solution
In [`download-mps.gradle`](../mps-gradle-scripts/gradle/download-mps.gradle), an automatic symbolic link is created after plugin extraction:
```groovy
def legacyDeps = file("$buildDir/dependencies")
if (!legacyDeps.exists()) {
    try {
        java.nio.file.Files.createSymbolicLink(legacyDeps.toPath(), outputDependenciesDirectory.toPath())
    } catch (Exception e) {
        // Fallback for environments where symlink creation is restricted
    }
}
```

---

## 3. Plugin Loading Failure: IDEA Build Range Incompatibility

### Symptom
MPS starts up cleanly, but installed or bundled plugins fail to load with warnings like:
```
Plugin 'de.vimotest' is incompatible with this version of the IDE
```

### Root Cause
The plugin's `plugin.xml` or generated build script has a restrictive `<idea-version>` range, such as:
```xml
<idea-version since-build="253" until-build="253.*"></idea-version>
```
MPS 2026.1 reports its platform build as `261.*`.

### Solution
Update the build solution or `build.xml` to match the target 2026.1 build range:
```xml
<idea-version since-build="261" until-build="261.*"></idea-version>
```

---

## 4. Itemis Extensions Compatibility for MPS 2026.1

### Symptom
Model validation or generation fails with unresolved nodes referencing `de.slisson.mps.richtext`:
```
Model de.slisson.mps.richtext.customcell... can't resolve node
```

### Root Cause
Using an outdated build of Itemis MPS Extensions built against MPS 2025.x.

### Solution
In `mps-gradle-scripts/build.gradle` and downstream repositories using Itemis extensions, specify the verified 2026.1 release version:
```groovy
ext.mpsPlugins = [
    "mbeddr-platform": "2026.1.3712.45fabf4"
]
```

---

## 5. Generator Reduction Rule: Broken Reference on `MemberReference`

### Symptom
During ALFI generation in `mps-alfi`:
```
While reducing Name expression: Target does not map to a IReferencableMemberDeclaration
Broken reference 'memberDeclaration' in concept MemberReference
```

### Root Cause
In `mps-alfi/languages/alfi.toCsBaseLanguage`, the reduction rule for optional value coalescing (`NameExpression`) generated a `MemberReference` node (`1VUwCF`) when resolving a variable name, and checked against `IReferencableMemberDeclaration`. Because the target was a local variable, not a member field or method, the reference target was invalid.

### Solution
Switch the generator template to use `VariableReference` (`3UcWq5`) in role `variableDeclaration` (`zF7P4`), checking against `IReferencableVariableDeclaration`.

---

## 6. Tag Naming Format: Prohibited `v` Prefix

### Symptom
Release tags like `v2026.1.0` break downstream dependency download URLs and clash with repository history.

### Root Cause
The ViMoTest ecosystem historically uses bare versions for all release tags:
- `2024.3.0`, `2025.1.0`, `2025.3.0`, `2025.3.1`, `2025.3.2-beta1`, etc.
- Standard GitHub release URLs expect: `.../releases/download/<version>/...` without any `v` prefix.

### Rule
**Never** use a `v` prefix. Always tag releases as:
```bash
git tag -a 2026.1.0 -m "Release 2026.1.0"
```

