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

1. Open a project.
2. Open the **AI Context** tool window (right side).
3. Click **1. Scan project** at the top of the tool window.
4. Expand folders and check the files you want. Click **Show filters** only if you need categories, keywords, filenames, or paths. You can also right-click a file and choose **Add to AI Context**.
5. Click **3. Export selected files**.
6. Open `prompt.md` (Agent Contract) and attach the bundles to your assistant.

## Mapping to `baic`

This Host covers the same workflow as the `baic` CLI: scan, filter (category / path / keyword), redact, secret skip, oversized-file handling, filetree, code graph, and project overview.

Settings live under **Settings → Tools → Build AI Context** (max file lines, output directory, redact, secret-like files, project overview, write graph, update `.gitignore`).
