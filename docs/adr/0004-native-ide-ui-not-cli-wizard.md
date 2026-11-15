# Native IDE UI, not a cloned CLI wizard

The CLI's five-step menu exists because a terminal has no file tree, no multi-select explorer, and no persistent panel. An IDE has all three. Cloning the wizard (especially into a Webview) fights both platforms' UX rules: VS Code says do not use webviews for wizards and prefer Tree Views ([UX guidelines](https://code.visualstudio.com/api/ux-guidelines/webviews), [views](https://code.visualstudio.com/api/ux-guidelines/views)); IntelliJ expects a Tool Window, Actions, and ProgressIndicator ([tool windows](https://plugins.jetbrains.com/docs/intellij/tool-windows.html)).

v1 UI is a persistent Source-Control-like panel: composed filters, a checkable file tree, Export on the toolbar, progress in the IDE's progress API, results as a notification with "Reveal" / "Open Agent Contract". Do not clone the CLI wizard into a webview.

## Amendment (2026-11-18)

VS Code TreeView cannot render the export-first mockup (inline search, file-format dropdown, full-width Export) at 250–350 px. v1 VS Code chrome is a themed `WebviewView` (`baic.panel`) that follows IDE colors. It is still a persistent panel, not a wizard. Android Studio stays on native Swing. A later Code Graph visualization may use a webview on either Host.
