# Build AI Context (IntelliJ Platform)

Export the open project into AI-readable text bundles without installing Python.
Works in IntelliJ IDEA, Android Studio, WebStorm, PyCharm, and other IntelliJ Platform IDEs.

This Host is not on the JetBrains Marketplace yet. Package locally and install from disk.

## Install from disk

From the repo root (or `ide/intellij`):

```bash
cd ide/intellij
./gradlew :plugin:buildPlugin
```

The zip is written to:

`ide/intellij/plugin/build/distributions/plugin-0.1.0.zip`

Then in the IDE:

1. **Settings → Plugins**
2. Gear menu → **Install Plugin from Disk…**
3. Select `plugin-0.1.0.zip`
4. Restart when prompted

No Python, Node, or separate JRE is required beyond the IDE itself.

## Use

1. Open a project. The catalog loads with it.
2. Open the **AI Context** tool window (right side).
3. Search file names, paths, or categories; choose a file format to narrow the results; then **Select all results** or check individual files. **Show options** has content keywords, explicit paths, ignored paths, and split.
4. Click **Export**. Only checked files in the current results are exported. gzip is the default and writes `baic_prompt.md`.
5. **Restore gzip** unpacks a previous export.

## Mapping to `baic`

This Host covers the same workflow as the `baic` CLI: catalog, search and file-format filtering, selection by category / path / content keyword, gzip or text transport, restore, redact, secret skip, oversized-file handling, filetree, code graph, and project overview.

Settings live under **Settings → Tools → Build AI Context** (transport, output directory, force-bundle, exclude paths, update `.gitignore`, and the rest).
