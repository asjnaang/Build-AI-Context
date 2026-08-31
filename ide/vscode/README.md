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

1. Open a folder.
2. Open the **AI Context** view in the Activity Bar.
3. Run **Build AI Context: Scan**.
4. Toggle categories or right-click a file **Add to AI Context**.
5. Run **Build AI Context: Export**.
6. Open `prompt.md` (Agent Contract) and attach the bundles to your assistant.

## Mapping to `baic`

This Host covers the same workflow as the `baic` CLI: scan, filter (category / path / keyword), redact, secret skip, oversized-file handling, filetree, code graph, and project overview.

Settings live under **Build AI Context** (`baic.*`).
