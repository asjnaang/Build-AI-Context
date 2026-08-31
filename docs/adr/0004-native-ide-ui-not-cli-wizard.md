# Native IDE UI, not a cloned CLI wizard

The CLI's five-step menu exists because a terminal has no file tree, no multi-select explorer, and no persistent panel. An IDE has all three. Cloning the wizard (especially into a Webview) fights both platforms' UX rules: VS Code says do not use webviews for wizards and prefer Tree Views ([UX guidelines](https://code.visualstudio.com/api/ux-guidelines/webviews), [views](https://code.visualstudio.com/api/ux-guidelines/views)); IntelliJ expects a Tool Window, Actions, and ProgressIndicator ([tool windows](https://plugins.jetbrains.com/docs/intellij/tool-windows.html)).

v1 UI is a persistent Source-Control-like panel: composed filters, a checkable file tree, Export on the toolbar, progress in the IDE's progress API, results as a notification with "Reveal" / "Open Agent Contract". Webviews are out of v1 except if a later version visualizes a Code Graph.
