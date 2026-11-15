# Build AI Context (VS Code)

Export the open workspace into AI-readable text bundles without installing Python.

This Host is not on the VS Code Marketplace or Open VSX yet. Package locally and install from a VSIX.

## Install from VSIX

From the repo root:

```bash
npm --prefix ide/vscode run package
```

That produces:

`ide/vscode/build-ai-context-0.1.0.vsix`

Then in VS Code:

1. Command Palette → **Extensions: Install from VSIX…**
2. Select `build-ai-context-0.1.0.vsix`
3. Reload when prompted

No Python install is required; VS Code already provides Node for the extension host.

## Use

1. Open a folder. The catalog loads with it.
2. Open the **AI Context** view in the Activity Bar (**Files**, **Options**, **Last export**).
3. In **Options**, search file names, paths, or categories; choose a file format to narrow the results; then **Select all results** or check individual files. Content keywords and explicit paths are separate selectors.
4. Click **Export** in Files. Only checked files in the current results are exported. gzip is the default and writes `baic_prompt.md`.
5. **Restore gzip** unpacks a previous export.

## Mapping to `baic`

This Host covers the same workflow as the `baic` CLI: catalog, search and file-format filtering, selection by category / path / content keyword, gzip or text transport, restore, redact, secret skip, oversized-file handling, filetree, code graph, and project overview.

Settings live under **Build AI Context** (`baic.*`).
