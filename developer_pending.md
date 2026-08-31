# Developer pending — publish Hosts to the public

Human-only work. Agents must not create marketplace accounts, store PATs, or run `vsce publish` / `ovsx publish` / Marketplace upload from this machine. Plan **D18**: package locally and in CI; publishing waits until you create the publisher identities.

Cited research notes (same sources): [`docs/ide-plugins/research-marketplace-publish.md`](docs/ide-plugins/research-marketplace-publish.md).

This file is the checklist after `feat/ide-plugins` is code-complete. Identifiers already in the tree:

| Surface | Value | Change after first public release? |
|---|---|---|
| VS Code / Open VSX publisher id | `asjnaang` (`ide/vscode/package.json`) | **No** — Marketplace ID cannot change once created. Create the publisher with this exact ID, or change the field *before* the first upload. |
| Extension name | `build-ai-context` | **No** after Marketplace has it. Combined id is `asjnaang.build-ai-context`. |
| Display name | Build AI Context | Display names must stay unique on Marketplace. |
| IntelliJ plugin XML id | `com.asjnaang.buildaicontext` | **No** after public release ([plugin.xml `id`](https://plugins.jetbrains.com/docs/intellij/plugin-configuration-file.html)). |
| JetBrains vendor display | ASJN | Vendor *profile* is created on first Marketplace upload; `plugin.xml` `<vendor>` is listing metadata. |
| Host version | `0.1.0` | Increment on every upload. Marketplace rejects reuse of a deleted version. |
| Source repo | https://github.com/asjnaang/Build-AI-Context | Public. Open-source license (MIT) uploads to JetBrains Marketplace require a source URL. |

Do not publish until you have dogfooded the local packages below on a real project (the `small-py` fixture at `ide/testdata/workspaces/small-py` is the minimum).

---

## 0. What is already done in the repo

- TypeScript Engine + Kotlin Engine with golden parity against current `baic`.
- VS Code Host (`ide/vscode`) and IntelliJ Platform Host (`ide/intellij/plugin`).
- MIT `LICENSE` inside the VSIX; `CHANGELOG.md`; PNG Marketplace icon (`ide/vscode/media/icon.png`, ≥128×128, not SVG).
- IntelliJ `pluginIcon.svg` / `pluginIcon_dark.svg` under `META-INF/` (40×40 SVG, required for Plugin Manager + Marketplace logo).
- CI (`.github/workflows/ide-hosts.yml`) tests both engines and **uploads** a VSIX and `plugin-0.1.0.zip` as GitHub Actions artifacts. It does **not** publish.

Still yours: accounts, tokens, first upload, Marketplace review, then README “preview” → public links.

---

## 1. Test locally (before any account)

### Automated (from repo root)

```bash
PYTHONPATH=src python3 -m pytest tests/test_policy_lock.py -q
npm --prefix ide/engine-ts test
npm --prefix ide/vscode test
JAVA_HOME="$(/usr/libexec/java_home -v 21 2>/dev/null || echo /Library/Java/JavaVirtualMachines/jdk-21.jdk/Contents/Home)"
(cd ide/intellij && JAVA_HOME="$JAVA_HOME" ./gradlew :engine:test --no-daemon)
```

### Package

```bash
npm --prefix ide/vscode run package
# → ide/vscode/build-ai-context-0.1.0.vsix

(cd ide/intellij && JAVA_HOME="$JAVA_HOME" ./gradlew :plugin:buildPlugin --no-daemon)
# → ide/intellij/plugin/build/distributions/plugin-0.1.0.zip
```

Or download the same artifacts from the `ide-hosts` GitHub Action.

### VS Code / Cursor / VSCodium — Install from VSIX

1. Open the fixture: `ide/testdata/workspaces/small-py` as a folder. **Trust** the workspace (scan/export are disabled until trusted).
2. Command Palette → **Extensions: Install from VSIX…** → `ide/vscode/build-ai-context-0.1.0.vsix`.
3. Reload. Open the **AI Context** view in the Activity Bar.
4. **Build AI Context: Scan**. You should see `python` / `config_docs`, `README.md`, `main.py`, `src/util.py`. `.env` and `node_modules/skip.js` stay out.
5. **Build AI Context: Export**. Open `prompt.md` (Agent Contract). Confirm a `*_bundle_001_*.txt` and `*_manifest_*.json` exist under `exported_sources_small-py_*`.
6. Optional: **Generate Filetree** / **Generate Code Graph** — files appear next to the folder root; `.gitignore` gains the same patterns as CLI `--tree`/`--graph` when `baic.updateGitignore` is on.

CLI install (VS Code): `code --install-extension ide/vscode/build-ai-context-0.1.0.vsix`

Uninstall: Extensions view → Build AI Context → Uninstall.

### IntelliJ Platform — Install from Disk

1. **File → Open** the fixture `ide/testdata/workspaces/small-py` as a project.
2. **Settings → Plugins → gear → Install Plugin from Disk…** → `ide/intellij/plugin/build/distributions/plugin-0.1.0.zip`.
3. Restart. Open tool window **AI Context** (right).
4. **Build AI Context: Scan** (Tools menu or toolbar). Toggle categories; **Export**.
5. Notification: **Reveal** / **Open Agent Contract**.
6. Tools menu: **Generate Filetree** / **Generate Code Graph**.

Optional sandbox without installing into your daily IDE:

```bash
(cd ide/intellij && JAVA_HOME="$JAVA_HOME" ./gradlew :plugin:runIde --no-daemon)
```

That downloads IntelliJ IDEA Community **2024.3.6** on first run, then opens a throwaway IDE with the plugin already loaded. Open `small-py` there.

Works in IDEA, Android Studio, WebStorm, PyCharm, etc., because the plugin depends only on `com.intellij.modules.platform`.

### Manual pass/fail

| Check | Pass |
|---|---|
| No Python on PATH required | Hosts still scan/export |
| Secrets | `.env` skipped unless you confirm include-secret-files |
| Oversized | A ≥3000-line file is warned/unchecked; checking it includes it |
| Untrusted VS Code window | Scan/export/filetree/graph do not write |
| Cancel export | `.gitignore` unchanged |

---

## 2. Create the three publisher identities

You need **three** logins. They are different companies. Use the same public name `asjnaang` / **ASJN** everywhere so listings look like one product.

### A. Visual Studio Marketplace (VS Code)

Primary source (accessed 2026-08-31): [Publishing Extensions](https://code.visualstudio.com/api/working-with-extensions/publishing-extension).

1. Microsoft account (the same one you will use for Azure DevOps).
2. Azure DevOps organization, if you do not have one: [Create an organization](https://learn.microsoft.com/azure/devops/organizations/accounts/create-organization).
3. Personal Access Token (still documented for interactive `vsce`; **global PATs are retired 1 December 2026** — after that, use [Entra ID / workload identity](https://code.visualstudio.com/api/working-with-extensions/publishing-extension#secure-automated-publishing-to-visual-studio-marketplace) for CI):
   - Portal: [Azure DevOps](https://go.microsoft.com/fwlink/?LinkId=307137) → your org → user menu → **Personal access tokens** → **New Token**.
   - Organization: **All accessible organizations** (403s are usually this dropdown set to one org).
   - Scopes: **Show all scopes** → **Marketplace** → **Manage**.
   - Copy once. Store in a password manager, not the git repo, not chat logs.
4. Publisher (irreversible ID):
   - [https://marketplace.visualstudio.com/manage](https://marketplace.visualstudio.com/manage)
   - Sign in with the same Microsoft account.
   - **Create publisher**.
   - **ID** = `asjnaang` (must match `package.json` `publisher`). This becomes the URL slug and **cannot be changed**.
   - **Name** = display name (e.g. ASJN).
   - Accept the [Marketplace Publisher Agreement](https://learn.microsoft.com/azure/devops/extend/publish/overview).
5. Verify the token (does not upload the extension):

```bash
cd ide/vscode
npx vsce login asjnaang
# paste PAT when prompted
```

Expect: `The Personal Access Token verification succeeded for the publisher 'asjnaang'.`

Publisher verification badge (optional, later): you need the publisher to exist ≥6 months and an eligible HTTPS domain. Not required for first publish.

### B. Open VSX (Cursor, VSCodium, Gitpod, …)

Same VSIX, **same** `publisher` field `asjnaang`. Primary sources (2026): [Open VSX Publishing Extensions wiki](https://github.com/eclipse-openvsx/openvsx/wiki/Publishing-Extensions), [Publisher Agreement fix](https://blogs.eclipse.org/post/thomas-froment/open-vsx-%E2%80%9Cmust-log-eclipse-foundation-account%E2%80%9D-error-quick-fix) (9 Apr 2026), [Managing Namespaces](https://github.com/EclipseFdn/open-vsx.org/wiki/Managing-Namespaces) (edited 18 Aug 2026).

1. GitHub login at [https://open-vsx.org](https://open-vsx.org) (use the GitHub user that owns `asjnaang/Build-AI-Context`).
2. Eclipse Foundation account: [https://accounts.eclipse.org/user/register](https://accounts.eclipse.org/user/register) — **same GitHub identity**.
3. [https://open-vsx.org/user-settings/profile](https://open-vsx.org/user-settings/profile) → **Log in with Eclipse** → **Show Publisher Agreement** → **Agree**.
   - The Eclipse **Contributor** Agreement (ECA) is *not* this. Signing ECA does not allow publishing.
4. Create an Open VSX access token from the Open VSX user settings (token UI is on the registry after login). Store as `OVSX_PAT` in your password manager. The `ovsx` CLI also reads `OVSX_PAT`.
5. Create the namespace **before** the first publish (must equal `package.json` `publisher`):

```bash
npx ovsx create-namespace asjnaang -p "$OVSX_PAT"
```

Creating a namespace makes you a **contributor**, not automatically a **verified owner**. To mark listings verified, claim ownership (GitHub ID generally needs ≥1 year of history). If this namespace already exists as a VS Code Marketplace publisher, Open VSX asks you to show write access to that publisher.

Do not use a different publisher id on Open VSX. Cursor/VSCodium resolve `asjnaang.build-ai-context`.

### C. JetBrains Marketplace (IntelliJ Platform)

Primary sources (2026): [Uploading a new plugin](https://plugins.jetbrains.com/docs/marketplace/uploading-a-new-plugin.html) (20 Mar 2026), [Vendor profile](https://plugins.jetbrains.com/docs/marketplace/organizations.html), [Approval guidelines](https://www.jetbrains.com/legal/docs/plugins_site/approval-guidelines/) (v1.3, 31 Mar 2026), [Trader status](https://plugins.jetbrains.com/docs/marketplace/trader-status.html).

1. JetBrains Account: [https://account.jetbrains.com](https://account.jetbrains.com) (or sign-in from [https://plugins.jetbrains.com](https://plugins.jetbrains.com)).
2. First upload creates the **Vendor** profile:
   - Account menu → **Upload plugin**.
   - Accept the [JetBrains Marketplace Developer Agreement](https://plugins.jetbrains.com/legal/developer-agreement).
   - Create Vendor. Public name can be **ASJN**.
   - Declare **trader** vs **non-trader** (EU consumer rules). This is legal, not technical. A free plugin still needs the declaration. Traders must later supply identity + banking; non-traders are “peer-consumers.”
3. Vendor website + email must be valid ([approval 1.3.a](https://www.jetbrains.com/legal/docs/plugins_site/approval-guidelines/)). `plugin.xml` already has `url="https://github.com/asjnaang/Build-AI-Context"`. Add a real `email=` attribute (or fill it on the upload form) before you submit — do not invent one in git.
4. License on the upload form: **MIT**. Because it is open-source, paste the public repo URL.
5. Tags: pick ones that match “export / AI / source code” — wrong tags hurt search and can delay review.
6. Leave **Custom Release Channel** empty for the public Stable channel. Check **Hidden** only if you want approval without going public yet ([hidden plugin](https://plugins.jetbrains.com/docs/marketplace/hidden-plugin.html)).
7. Ads: leave undeclared / false. This Host has no ads.
8. Logo: not the IntelliJ Plugin Template default. `pluginIcon.svg` is in the zip. You can also attach a Marketplace logo on the form if asked.
9. Plugin Verifier: every upload is checked for binary compatibility with the claimed IDE range (`sinceBuild=243`, no `until-build`). If verifier fails, the listing is not approved.

Numeric plugin id (e.g. `plugins.jetbrains.com/plugin/NNNN-…`) appears **after** the first upload. You need that number (or the XML id) for later API uploads.

Optional API token for later updates: Marketplace profile → **My Tokens** → `permanentToken`. Header: `Authorization: Bearer <token>`. First upload is the web form; API is for updates ([plugin upload API](https://plugins.jetbrains.com/docs/marketplace/plugin-upload.html)).

Paid/`<product-descriptor>`: do **not** add. This Host is free.

---

## 3. First public upload (after local dogfood)

Order: Marketplace VSIX → same VSIX to Open VSX → JetBrains zip. That way Cursor users and VS Code users get the same bytes.

### 3.1 Visual Studio Marketplace

Package once:

```bash
npm --prefix ide/vscode run package
```

**Web (safest first time):** [manage publishers](https://marketplace.visualstudio.com/manage) → publisher `asjnaang` → **New extension** → upload `ide/vscode/build-ai-context-0.1.0.vsix` → fill listing if prompted → **Save**. Then **Make Public** when you are ready (the VS *full* Marketplace walkthrough uses that wording; VS Code listings appear after validation).

**CLI:**

```bash
cd ide/vscode
npx vsce publish
# or: npx vsce publish --packagePath build-ai-context-0.1.0.vsix
```

`vsce` refuses: SVG as `package.json` `icon` (we ship PNG); SVG images in README/CHANGELOG except trusted badges; `http://` image URLs. Current README has no images.

If `vsce publish` also creates a git tag, that is expected (`npm version` behavior). You can pass `-m "release vscode 0.1.0"`.

Common 403: PAT Organization was not **All accessible organizations**, or scope was not Marketplace **Manage**.

Do not delete a listing to “reset the name.” Removal **permanently reserves** the extension name.

### 3.2 Open VSX (same VSIX)

```bash
npx ovsx publish ide/vscode/build-ai-context-0.1.0.vsix -p "$OVSX_PAT"
```

Namespace `asjnaang` must already exist (step 2.B.5).

### 3.3 JetBrains Marketplace

Upload `ide/intellij/plugin/build/distributions/plugin-0.1.0.zip` (the `plugin-provider(?).zip` sibling in `distributions/` is leftover Gradle noise — ignore it).

[Upload plugin](https://plugins.jetbrains.com/docs/marketplace/uploading-a-new-plugin.html) → choose Vendor ASJN → attach zip → MIT + source URL → tags → submit.

Review: paid/freemium targets two business days in the [release](https://plugins.jetbrains.com/docs/marketplace/release-plugin.html) doc; free plugins still go through [approval](https://www.jetbrains.com/legal/docs/plugins_site/approval-guidelines/). Watch email on the JetBrains account.

If they reject for vendor email / logo / description length, fix `plugin.xml`, rebuild the zip, upload an update. Plugin XML **id** stays `com.asjnaang.buildaicontext`.

---

## 4. After they are public

1. Root `README.md` “IDE Hosts (preview)” — replace “not on the marketplaces yet” with:

   - VS Code: `https://marketplace.visualstudio.com/items?itemName=asjnaang.build-ai-context`
   - Open VSX: `https://open-vsx.org/extension/asjnaang/build-ai-context`
   - JetBrains: `https://plugins.jetbrains.com/plugin/<numeric-id>-build-ai-context` (copy from the listing)

2. `ide/vscode/README.md` and `ide/intellij/plugin/README.md` — same links; keep Install from VSIX / Disk as a fallback.

3. Next version: bump `ide/vscode/package.json` `version` **and** `ide/intellij/gradle.properties` `version` (they are independent of PyPI `1.0.12`). Add CHANGELOG / `<change-notes>`. Never reuse a yanked Marketplace version number.

4. CI publish (optional, later — not on this branch):
   - GitHub Actions secrets: `VSCE_PAT` (or Entra federation after 2026-12-01), `OVSX_PAT`, JetBrains `JETBRAINS_MARKETPLACE_TOKEN`.
   - Names must match `secrets.*` exactly. Never commit the values.
   - Open VSX example job: [Auto-publishing](https://github.com/EclipseFdn/open-vsx.org/wiki/Auto-Publishing-Extensions) uses `OVSX_PAT: ${{ secrets.OVSX_PAT }}` and `npx ovsx publish dist/*.vsix`.
   - Prefer publishing **from CI artifacts** of `ide-hosts.yml` so you ship the same zip/vsix you tested.

5. Do not add Copilot/chat upload, telemetry, or Visual Studio (full) in the same listing. Those are out of the Host contract.

---

## 5. You vs an agent

| Step | Who |
|---|---|
| Tests, package, CI artifacts | Agent / you locally |
| Microsoft, Eclipse, JetBrains accounts | **You** |
| Publisher ID `asjnaang`, namespace, Vendor profile | **You** (irreversible) |
| PAT / Open VSX token / Marketplace permanentToken | **You** (password manager) |
| `vsce login`, first `vsce publish`, `ovsx publish`, JetBrains web upload | **You** |
| Trader/non-trader, EULA/MIT confirmation, agreements | **You** |
| Vendor email in `plugin.xml` | **You** (real address) |
| README marketplace URLs after approval | Either, once URLs exist |

If an agent offers to “just publish,” the answer is no until this file’s account sections are done by you.

---

## Sources (accessed 2026-08-31)

- https://code.visualstudio.com/api/working-with-extensions/publishing-extension
- https://learn.microsoft.com/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate
- https://marketplace.visualstudio.com/manage
- https://github.com/eclipse-openvsx/openvsx/wiki/Publishing-Extensions
- https://github.com/EclipseFdn/open-vsx.org/wiki/Managing-Namespaces
- https://blogs.eclipse.org/post/thomas-froment/open-vsx-%E2%80%9Cmust-log-eclipse-foundation-account%E2%80%9D-error-quick-fix
- https://accounts.eclipse.org/user/register
- https://open-vsx.org/user-settings/profile
- https://plugins.jetbrains.com/docs/marketplace/uploading-a-new-plugin.html
- https://plugins.jetbrains.com/docs/marketplace/organizations.html
- https://plugins.jetbrains.com/docs/intellij/plugin-configuration-file.html
- https://plugins.jetbrains.com/docs/intellij/plugin-icon-file.html
- https://www.jetbrains.com/legal/docs/plugins_site/approval-guidelines/
- https://plugins.jetbrains.com/docs/marketplace/plugin-upload.html
