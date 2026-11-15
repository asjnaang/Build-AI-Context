# IDE plugins: local trial and publishing

The VS Code extension and Android Studio plugin run without Python. The current `0.1.0` packages are local builds of `feat/ide-plugins` until the marketplace listings go live. Visual Studio Marketplace hosts the **VS Code** listing. These packages do not target the full Visual Studio IDE.

Human publish (accounts, agreements, first JetBrains upload):

```bash
bash ide/scripts/publish-marketplaces.sh
```

Primary-source notes: [`docs/ide-plugins/research-marketplace-publish.md`](docs/ide-plugins/research-marketplace-publish.md). Layout: [`docs/ide-plugins/ui-spec-2026-11-16.md`](docs/ide-plugins/ui-spec-2026-11-16.md).

## 1. Try locally

Build from the repository root, or download the `ide-hosts` GitHub Actions artifacts:

```bash
npm --prefix ide/vscode test
npm --prefix ide/vscode run package
(cd ide/intellij && ./gradlew :engine:test :plugin:buildPlugin --no-daemon)
```

| IDE | Install | Try |
| --- | --- | --- |
| VS Code | Extensions → `…` → **Install from VSIX…** → `ide/vscode/build-ai-context-0.1.0.vsix`; reload | Open and trust a project. Open **AI Context** in the Activity Bar. Search/filter, then **Export N files**. |
| Android Studio | Settings → Plugins → gear → **Install Plugin from Disk…** → `ide/intellij/plugin/build/distributions/plugin-0.1.0.zip`; restart | Open a project. Open **AI Context** on the right. Search/filter, then **Export N files**. |

The same VSIX and ZIP install on Windows. Use a project copy when testing Export: it creates `exported_sources_*` and may update `.gitignore` unless `baic.updateGitignore` / the matching setting is off. `ide/testdata/workspaces/small-py` is a quick check; `~/WORK/Samples` has realistic Android projects. Keep sample git trees clean: set output under `~/WORK/Samples/outputs` and disable gitignore updates.

### Local results (2026-11-15)

- Installed both packages on this Mac. VS Code and Android Studio each scanned and exported the small fixture through their UI. Fixed a VS Code workspace trust command condition and an Android Studio tree refresh crash found during this trial, then rebuilt and retested.
- Scanned all four projects in `~/WORK/Samples` with the extension's TypeScript engine, then exported to a temporary directory with redaction, project overview, and JSON code graph enabled. `updateGitignore` was disabled, so these exports did not write to the sample repositories. Sunflower also scanned in the installed VS Code extension: `config_docs (34)`, `java_kotlin (78)`.

| Project | Scanned | Exported | Bundles | Oversized files skipped |
| --- | ---: | ---: | ---: | ---: |
| Sunflower | 112 | 111 | 2 | 1 |
| Now in Android | 489 | 487 | 7 | 2 |
| Wikipedia | 2,434 | 2,410 | 55 | 9 |
| AnkiDroid | 4,007 | 4,001 | 67 | 4 |

Oversized means at or above the default 3,000 line export limit. The exported count can also exclude empty files.

### CLI alias, split, and restore checks

Using this branch's Python CLI with output outside the sample repositories:

| Alias pattern | Result |
| --- | --- |
| `baica` (`--all` with your four `--exclude-paths`) | Sunflower selected 111 of 112 files; `docs/` was excluded. |
| `baick --keywords GardenActivity` | Selected 4 Sunflower files. |
| `baicp --paths app/build.gradle.kts` | Selected 1 Now in Android file. |
| `baicf --force-bundle --force-ignored --force-include-formats .sqlite3 --paths …` | Selected a 9,133-line Sunflower file and an ignored 1.4 MB SQLite file in a temporary sample-derived project. |
| `baicaf --all … --paths source-catalog.sqlite3` | Selected all 4 files in that temporary project. With `--all`, `--paths` adds ignored files but does **not** narrow selection. Remove `--all` if you intend to export only the named paths. |

All five compressed exports restored with **zero byte mismatches** against their selected source files. A second `--split` export of restored Sunflower selected the same 111 files and produced the same archive SHA-256. A focused test of a single file spanning multiple split payloads also passed. The installed Mac `baic` command reports `1.0.20` and does not expose `--restore`; these checks used `PYTHONPATH=src python3 -m build_ai_context.cli` from this branch. Update the installed CLI to a release containing restore before relying on that command in your shell.

**Host scope in 0.1.0:** search, file-format filter, category/path/keyword selection, gzip (default) and text transport, restore, exclude paths, force-ignored, force-bundle, extra formats, split, filetree, code graph, and overview. The panel is export-first: cataloging starts when the project opens.

## 2. Prepare the listings

1. Review the packages and feature scope. Rebuild after code changes. Increase the version for every later upload.
2. Confirm permanent IDs before first upload: VS Code publisher `asjnaang`, extension `build-ai-context` (`asjnaang.build-ai-context`); JetBrains plugin ID `com.asjnaang.buildaicontext`. Edit metadata first if these should differ.
3. Listing assets in-repo: VS Code icon `ide/vscode/media/icon.png` (256×256 PNG), screenshot `ide/vscode/media/screenshot.png`, JetBrains `pluginIcon.svg` in `META-INF`, screenshot `docs/ide-plugins/media/marketplace-1200x760.png`.
4. Prepare a public support email and vendor website, MIT license, source URL `https://github.com/asjnaang/Build-AI-Context`. The account owner must choose JetBrains trader status and accept marketplace agreements.

## 3. Publish to Visual Studio Marketplace (VS Code)

1. Sign in at [Marketplace management](https://marketplace.visualstudio.com/manage) with a Microsoft account. Create publisher ID **`asjnaang`**, matching `ide/vscode/package.json`. The ID cannot be changed after creation.
2. Choose **New extension → Visual Studio Code**, upload `ide/vscode/build-ai-context-0.1.0.vsix`, complete listing fields, and publish. Web upload avoids setting up a PAT for the first release.
3. Check `https://marketplace.visualstudio.com/items?itemName=asjnaang.build-ai-context`; install from Marketplace in a clean VS Code profile and repeat Export.

For later automated releases, follow [VS Code's trusted publishing guidance](https://code.visualstudio.com/api/working-with-extensions/publishing-extension#secure-automated-publishing-to-visual-studio-marketplace). Do not commit credentials. See the [official publishing guide](https://code.visualstudio.com/api/working-with-extensions/publishing-extension).

## 4. Publish to Open VSX (optional, Cursor / VSCodium)

Same publisher id `asjnaang` and extension name `build-ai-context`. Eclipse account + Open VSX Publisher Agreement, then `npx ovsx publish ide/vscode/build-ai-context-0.1.0.vsix -p <token>`. Details in the research note and the wizard.

## 5. Publish to JetBrains Marketplace (Android Studio)

1. Sign in at [JetBrains Marketplace](https://plugins.jetbrains.com/) and choose **Upload plugin**. The [first upload must be manual](https://plugins.jetbrains.com/docs/intellij/publishing-plugin.html). Create or select a vendor profile, accept the Developer Agreement, and declare trader or non-trader status.
2. Upload `ide/intellij/plugin/build/distributions/plugin-0.1.0.zip`. Set MIT license, public source URL, support email, vendor website, and relevant tags. Leave release channel empty for Stable. Add the 1200×760 screenshot. Submit for review. See [upload instructions](https://plugins.jetbrains.com/docs/marketplace/uploading-a-new-plugin.html) and [trader status](https://plugins.jetbrains.com/docs/marketplace/trader-status.html).
3. After approval, install from Marketplace in Android Studio and repeat Export on a project copy. For later releases, increment the version and use Marketplace upload or Gradle `publishPlugin` with a securely stored token.

After listings are live, replace preview language in repository READMEs with verified public links.
