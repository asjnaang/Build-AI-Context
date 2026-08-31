# Native IDE Hosts, not a Python GUI

People who cannot install or run Python cannot use `baic`, and they also cannot use the Flet GUI on `main_gui` (`src/anything_to_text/gui.py`), which is the same runtime with a different window. The product stays a Python CLI for people who have Python. Reach the rest with Hosts that run *inside* VS Code and IntelliJ Platform IDEs, with no Python (and no Node, and no JRE-in-VS-Code) required of the user.

**Considered options:** revive Flet; ship a PyInstaller binary and a thin UI; native IDE Hosts.

Flet still needs Python. A frozen binary solves "no pip" but not marketplace review, notarization, or in-process IDE UX. Native Hosts are the only option that matches how those users already work.
