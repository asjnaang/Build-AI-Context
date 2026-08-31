# VS Code and IntelliJ Platform in v1; not Visual Studio (full)

"IntelliJ" maps to the IntelliJ Platform: one plugin with `com.intellij.modules.platform` loads in IntelliJ IDEA, Android Studio, WebStorm, PyCharm, GoLand, Rider, CLion, PhpStorm, and the rest ([plugin compatibility](https://plugins.jetbrains.com/docs/intellij/plugin-compatibility.html)).

"VSStudio" is ambiguous. We treat it as **Visual Studio Code** (and VS Code-compatible editors via the Marketplace / Open VSX), not Visual Studio the Windows IDE. Visual Studio uses a different extensibility stack (VSSDK / VisualStudio.Extensibility, C#, Windows-centric) ([Microsoft Learn](https://learn.microsoft.com/en-us/visualstudio/extensibility/visualstudio.extensibility/extensibility-models?view=visualstudio)). That is a third Host, not a twin of VS Code.

v1 is two Hosts: VS Code extension + IntelliJ Platform plugin. Visual Studio (full) is deferred. If a later review says the original ask was Visual Studio 2022, that Host can sit on the same Engine contract; it is still a separate codebase.
