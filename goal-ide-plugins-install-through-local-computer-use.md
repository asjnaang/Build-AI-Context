# Goal: IDE plugin install through local computer-use

Read this file before touching IDE Hosts, Cua, Samples, or local-agentic-tools computer-use. If a step feels like progress but is not on this list, it is the wrong step.

## 1. What this work is

Two products, one playthrough.

**A. Local computer-use** so Grok, Claude, and Codex can see a native macOS app, click it, and keep working without cloud computer-use tokens.

**B. Build AI Context IDE Hosts** (VS Code + Android Studio / IntelliJ) so Windows users who have no Python still get the same bundling as Mac CLI users.

The playthrough that proves both: **build the Hosts, install them in the IDEs the human is looking at, using local computer-use, and export with the real engine and the right prompts.**

The human must see the Host in the window they already have open. A CLI install into a hidden profile, an isolated `--user-data-dir`, or a Marketplace search for someone else's extension is not the playthrough.

## 2. Why the Hosts exist

Mac CLI is already excellent. That is not the gap.

Windows laptop users cannot be asked to install Python. The VS Code VSIX and the IntelliJ/Android Studio zip exist so those users run Scan-as-engine-work plus **Export** inside the IDE.

Hosts hold **UI and IDE wiring only**. Core bundling stays one engine contract:

- Python `baic` = CLI Host and parity oracle
- TypeScript `ide/engine-ts` = in-process engine for VS Code (no Python)
- Kotlin `ide/intellij/engine` = in-process engine for Android Studio (no Python)

Do not fork bundling logic inside plugin UI. Do not shell out to Python from a Host. Policy, prompts, gzip/text transport, restore, and selection flags stay shared.

ADRs: `docs/adr/0001-native-ide-hosts-not-python-gui.md`, `0003-shared-engine-dual-in-process-ports.md`, `0004-native-ide-ui-not-cli-wizard.md`.

## 3. Local computer-use: home, shape, and visibility

**Home:** `/Users/user/WORK/Projects/local-agentic-tools` on branch `feat/computer-use`. Keep that branch off `main` until this playthrough and tests hold.

**Not home:**

- `/Users/user/WORK/Projects/Tools/computer-use` — leftover trial cache; remove if it reappears
- `/Users/user/WORK/github/Build-AI-Context/tools/computer-use` — do not put it here
- A skill-only folder with no CLI the human can open in Finder

The human asked to **see the whole development** in local-agentic-tools, the way it existed as a tool package: CLI, trials, tests, connect helper, skill, recipe. A skill file alone is incomplete.

Required layout:

```
local-agentic-tools/
  computer-use/cli.py
  computer-use/README.md
  computer-use/trials/
  skills/computer-use/SKILL.md
  skills/local-agentic-tools/references/computer-use.md
  tests/test_computer_use.py
```

Cua Driver (`cua-driver`) is the desktop clicker. This pack does **not** register a second computer-use MCP. `python3 computer-use/cli.py doctor|status|connect|call|trial-dir` wraps Cua.

Route table (token-efficient):

| Surface | Tool |
| --- | --- |
| Native IDE windows, Settings, installers | Cua Driver via `computer-use` |
| http(s) pages | browser recipe (Playwright / agent-browser) |
| Saved PNGs | image-efficient (`agentic-media text`) |
| PDFs | pdf-efficient |
| Source, git, tests | rg, git, pytest |

Forbidden while Cua is healthy: `open -a`, `osascript activate`, `cliclick`. Those steal the pointer. Background AX is the default. Bring a window forward only so the **human can see the Host**, which this playthrough requires.

## 4. What “install with computer-use” means

Drive the **same windows the human screenshots**.

Current human VS Code: title contains `nowinandroid` and profile `vscode_settings`. Marketplace “Build AI Context” listings (The Hung Dang and others) are **other publishers**. Our unpublished package is `asjnaang.build-ai-context` from `ide/vscode/build-ai-context-0.1.0.vsix`.

Current human Android Studio: nowinandroid under `/Users/user/WORK/Samples/nowinandroid`. Package id `com.asjnaang.buildaicontext` from `ide/intellij/plugin/build/distributions/plugin-0.1.0.zip`.

Playthrough:

1. Rebuild Hosts from `feat/ide-plugins` (VSIX + zip).
2. With Cua, in the visible VS Code window: Command Palette → **Extensions: Install from VSIX…** → that VSIX → reload if the IDE asks → Activity Bar **AI Context**.
3. With Cua, in the visible Android Studio window: **Settings → Plugins → Install Plugin from Disk…** (or equivalent) → that zip → restart if the IDE asks → right **AI Context** tool window.
4. Prove the Host UI: Files / Options / Export (no “you must Scan first” as the only path). Catalog may load with the folder; Export is the user action.
5. Export to `/Users/user/WORK/Samples/outputs/…` with `baic.updateGitignore` false. Sample git trees stay clean.
6. Gzip export writes `baic_prompt.md` from `baic_prompt_gzip.md`. Text export writes `baic_prompt.md` from `baic_prompt_text.md`. Restore gzip with `--restore` / Host Restore.

CLI install (`code --install-extension`) is allowed as a **non-GUI side path**, then Cua still has to open the Host in the human’s window. Isolated `--user-data-dir` trials are extra, not the proof the human asked for.

## 5. Host UI and engine behaviour (match the CLI)

The CLI is the product the human already trusts. Hosts expose that product visually.

Human CLI habits:

```sh
export baic_ignored="--exclude-paths history/,docs/,ios-runner/,tests/"
alias baick="baic --non-interactive --keywords"
alias baica="baic . --all $baic_ignored"
alias baicaf="baic . --all $baic_ignored --force-bundle --force-ignored --force-include-formats .sqlite3 --paths"
alias baicp="baic --non-interactive --paths"
alias baicf="baic --non-interactive --force-bundle --force-ignored --force-include-formats .sqlite3 --paths"
```

Hosts must offer the same capabilities without a five-step terminal wizard:

- Choose files on a checkable tree
- Options: transport **tar-gz (default)** vs **text**, `--exclude-paths`, `--force-bundle`, `--force-ignored`, `--force-include-formats`, `--split`, keywords, paths, `--all`
- One **Export** click runs the engine (catalog + bundle is seconds, like CLI)
- **Restore** for gzip (rebundle / `--restore`)
- Prompts from `src/build_ai_context/baic_prompt_gzip.md` and `baic_prompt_text.md`, output name `baic_prompt.md`

There is no separate user-facing “Scan section” as the product. Cataloging is engine work. A Refresh catalog control is fine. A wizard that says “1. Scan then 3. Export” is the wrong UI.

Bundling is fast. Do not poll a Scan progress UI for tens of seconds as if the tool were broken.

## 6. Samples and dirt

Bundled workspaces: `/Users/user/WORK/Samples/{sunflower,nowinandroid,ankidroid,wikipedia}`.

- VS Code fixture: sunflower (smaller) or the window the human has open
- Android Studio fixture: nowinandroid
- Exports: `/Users/user/WORK/Samples/outputs/…`
- `baic.updateGitignore=false`
- If a sample `.gitignore` still changes, restore it

## 7. Token and compact rules

At about **60%** of the session context window, compact with **`/local-compact`** (`agentic-llm compact` on the local Qwen3-14B-4bit). Do not wait for harness cloud `/compact` and do not treat cloud compact as the default.

`/local-compact` writes `compact.json` / `compact.md` on disk. It does not shrink the live Grok system/tool/image payload. After a harness compact of 300k→28k, a live 81k window is expected (prompt + skills + MCP + screenshots). Do not claim measured cloud-token billing savings.

Finishing a compact is **not** finishing the IDE playthrough.

## 8. Done means this, and only this

All of the following, with evidence the human can open:

1. `feat/computer-use` in local-agentic-tools contains the visible `computer-use/` package (CLI, trials, tests, skill, recipe). `Tools/computer-use` is absent.
2. `feat/ide-plugins` Hosts: VSIX and zip built from current sources.
3. **VS Code window the human uses** shows **AI Context** with our publisher `asjnaang`, Files/Options/Export, gzip default.
4. **Android Studio window the human uses** shows **AI Context** with `com.asjnaang.buildaicontext`, Export as the primary action.
5. One gzip Export from each Host lands under Samples/outputs with `baic_prompt.md` (gzip template) and a manifest `transport.format = tar+gzip+base64`.
6. Restore of that gzip export recovers source bytes (`computer-use` trial dir or Samples/outputs). Python `baic --restore` can restore a Host gzip export.
7. Sample git status is clean of `exported_sources*` / BAIC gitignore blocks.

Until 3–6 are true in the human’s windows, the playthrough is not done. Do not say it is done.

## 9. Mistakes this file exists to stop

- Putting computer-use under Tools or BAIC `tools/`, then leaving a leftover folder
- Shipping only a skill in local-agentic-tools
- Searching Marketplace for “build ai context” and installing another publisher
- Installing into Default profile while the window uses profile `vscode_settings`
- Isolated VS Code `--user-data-dir` as the only install, then telling the human it is installed
- Treating `/local-compact` or harness compact as the product task
- A Scan-first wizard; waiting minutes on Scan
- Writing old `prompt.md` instead of transport-specific `baic_prompt.md`
- Text-only Host engine while CLI default is tar-gz
- Dirtying Samples git trees
- Stealing the pointer with `open -a` / AppleScript / cliclick
- A second Python computer-use MCP next to cua-driver
- Claiming Electron `unverifiable` clicks as success without tree/files/OCR proof
- Merging `feat/computer-use` to main before this playthrough holds

## 10. Branches, packages, commands

| Item | Value |
| --- | --- |
| BAIC branch | `feat/ide-plugins` |
| LAT branch | `feat/computer-use` |
| VS Code package | `asjnaang.build-ai-context` `ide/vscode/build-ai-context-0.1.0.vsix` |
| IntelliJ package | `com.asjnaang.buildaicontext` `ide/intellij/plugin/build/distributions/plugin-0.1.0.zip` |
| Computer-use CLI | `python3 /Users/user/WORK/Projects/local-agentic-tools/computer-use/cli.py` |
| Cua | `cua-driver` 0.51.5, session label `baic-hosts` |
| Proof shots | `local-agentic-tools/computer-use/trials/` and `Samples/outputs/ide-trial/shots/` |

Rebuild:

```sh
npm --prefix ide/vscode run package
(cd ide/intellij && ./gradlew :plugin:buildPlugin --no-daemon)
python3 /Users/user/WORK/Projects/local-agentic-tools/computer-use/cli.py doctor
```

## 11. How to use this file

At the start of a turn on this work, re-read sections 1, 4, 8, and 9. If the last action would fail section 8, do not report success. Drive Cua on the human’s windows until 3–6 are proven with a saved PNG plus files on disk.
