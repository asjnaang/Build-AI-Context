# IDE Host platforms — cited notes (2026-08-31)

Primary-source notes used while grilling the Host plan. Claims below point at the owning docs.

## VS Code vs Visual Studio

Microsoft treats them as different products. Visual Studio extensibility is C# / VSIX / Windows; VS Code authors are sent to `code.visualstudio.com/api`.

- https://code.visualstudio.com/docs/supporting/faq
- https://learn.microsoft.com/en-us/visualstudio/extensibility/starting-to-develop-visual-studio-extensions?view=visualstudio
- https://learn.microsoft.com/en-us/visualstudio/extensibility/visualstudio.extensibility/extensibility-models?view=visualstudio

## VS Code UX (native trees, no webview wizards)

- Overview: https://code.visualstudio.com/api/ux-guidelines/overview
- Views / Tree View: https://code.visualstudio.com/api/ux-guidelines/views
- Webviews — do not use for wizards: https://code.visualstudio.com/api/ux-guidelines/webviews
- Quick Picks — not long wizards: https://code.visualstudio.com/api/ux-guidelines/quick-picks
- Settings belong in `contributes.configuration`: https://code.visualstudio.com/api/ux-guidelines/settings
- Tree View API: https://code.visualstudio.com/api/extension-guides/tree-view
- Publishing / platform-specific VSIX: https://code.visualstudio.com/api/working-with-extensions/publishing-extension
- Workspace extensions for Remote/Codespaces: https://code.visualstudio.com/api/advanced-topics/remote-extensions
- Web extensions cannot spawn processes: https://code.visualstudio.com/api/extension-guides/web-extensions
- Marketplace signing / same OS rights as the editor: https://code.visualstudio.com/docs/configure/extensions/extension-runtime-security

Cursor and VSCodium consume **Open VSX**, not the Visual Studio Marketplace.

- https://cursor.com/help/customization/extensions
- https://github.com/VSCodium/vscodium/blob/master/docs/extensions.md
- https://www.eclipse.org/legal/open-vsx-registry-faq/

## IntelliJ Platform

- One plugin, many IDEs via `com.intellij.modules.platform`: https://plugins.jetbrains.com/docs/intellij/plugin-compatibility.html
- Tool windows (lazy factory): https://plugins.jetbrains.com/docs/intellij/tool-windows.html
- Actions: https://plugins.jetbrains.com/docs/intellij/action-system.html
- Progress / `Task.Backgroundable`: https://plugins.jetbrains.com/docs/intellij/background-processes.html
- Plugin UX (no setup wizard, settings in Settings, Swing default, JCEF last): https://plugins.jetbrains.com/docs/intellij/plugin-user-experience.html
- No OS-specific Marketplace ZIPs: https://plugins.jetbrains.com/docs/intellij/plugin-content.html
- Upload size 400 MB; human review of every update: https://plugins.jetbrains.com/docs/marketplace/uploading-a-new-plugin.html
- Approval: https://plugins.jetbrains.com/legal/approval-guidelines

## Shared-engine industry pattern

Language tools bundle a native binary and speak JSON-RPC/LSP. Users do not install Python.

- rust-analyzer: https://rust-analyzer.github.io/book/installation.html
- Ruff (bundled native server; Python LSP deprecated): https://github.com/astral-sh/ruff-vscode/blob/main/README.md
- clangd: https://clangd.llvm.org/installation
- LSP: https://code.visualstudio.com/api/language-extensions/language-server-extension-guide

This plan uses **in-process TypeScript + Kotlin ports** for v1 (no extra runtime, no per-OS Marketplace artifacts). The native-binary pattern is the documented revisit if dual-port drift appears (`plan.md` D4).
