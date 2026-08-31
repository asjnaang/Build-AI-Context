# Research: Publishing IDE plugins to marketplaces

**Access date:** 2026-08-31  
**Scope:** Human-first publish paths for this repo’s VS Code extension and IntelliJ plugin. Primary sources only (Microsoft / Azure DevOps, Eclipse Open VSX, JetBrains).

**Assumed package identity (do not invent others):**

| Host | Identity |
| --- | --- |
| VS Code / Open VSX | publisher `asjnaang`, name `build-ai-context`, displayName `Build AI Context`, version `0.1.0`, engines `vscode ^1.90.0`, MIT, package script `vsce package` |
| IntelliJ | plugin id `com.asjnaang.buildaicontext`, vendor ASJN, platform IC 2024.3.6, `pluginSinceBuild` 243, `untilBuild` null, Gradle IntelliJ Platform Plugin 2.x, `./gradlew :plugin:buildPlugin` |

---

## 1. Visual Studio Marketplace (VS Code)

### Account / identity required

- Marketplace auth and hosting go through **Azure DevOps**. Extensions are published under a **publisher** tied to a **Microsoft account** (same account used for the Azure DevOps PAT). ([Publishing Extensions](https://code.visualstudio.com/api/working-with-extensions/publishing-extension))
- Create an Azure DevOps organization if you do not have one: sign in at [https://go.microsoft.com/fwlink/?LinkId=307137](https://go.microsoft.com/fwlink/?LinkId=307137) → **New organization**. Identity may be a personal Microsoft account, GitHub account, or work/school account. Organization creation is manual (web portal only). ([Create an organization](https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/create-organization))
- Publisher management UI: [https://marketplace.visualstudio.com/manage](https://marketplace.visualstudio.com/manage) — log in with the same Microsoft account used for the PAT. ([Publishing Extensions — Create a publisher](https://code.visualstudio.com/api/working-with-extensions/publishing-extension#create-a-publisher))

### Publisher ID rules (irreversible)

- Create publisher at the manage page → **Create publisher**.
- Mandatory fields:
  - **ID**: unique Marketplace identifier used in extension URLs. **“ID cannot be changed once created.”**
  - **Name**: display name (company/brand); documented as unique for display with your extensions.
- For this repo the irreversible choice is publisher **`asjnaang`** (must match `package.json` `"publisher"`).
- Extension `name` and `displayName` must each be unique across the Marketplace. ([Extension Manifest](https://code.visualstudio.com/api/references/extension-manifest))
- Removing an extension permanently reserves its name (cannot be reused, even by the original publisher). Unpublish preserves stats; remove deletes stats. Version deletion is irreversible and that version number cannot be reused; latest version cannot be deleted. ([Publishing Extensions](https://code.visualstudio.com/api/working-with-extensions/publishing-extension))

### Personal Access Token (PAT)

Steps from official docs ([Get a Personal Access Token](https://code.visualstudio.com/api/working-with-extensions/publishing-extension#get-a-personal-access-token)):

1. Azure DevOps portal → select organization.
2. User settings (next to profile image) → **Personal access tokens** → **New Token**.
3. Token settings:
   - **Name**: any
   - **Organization**: **All accessible organizations** (specific org → common 403/401)
   - **Scopes**: **Custom defined** → **Show all scopes** → **Marketplace** → **Manage**
4. **Create**, copy immediately, store securely (used for `vsce login` / publish).

**Important (time-sensitive):** Global PATs in Azure DevOps are **retired on December 1, 2026**. Microsoft recommends Microsoft Entra ID / workload identity federation for automated publishing (`vsce publish --azure-credential`, vsce ≥ 2.26.1). ([Publishing Extensions](https://code.visualstudio.com/api/working-with-extensions/publishing-extension); [Retirement of global PATs](https://devblogs.microsoft.com/devops/retirement-of-global-personal-access-tokens-in-azure-devops/))

`vsce` stores login state after `vsce login <publisher id>` (prompts for PAT). For CI, do **not** rely on interactive login; use env secret (below).

### Package / upload: CLI vs web UI

| Path | How |
| --- | --- |
| CLI package | `npm install -g @vscode/vsce` then `vsce package` (repo script: `vsce package --allow-missing-repository`) → `.vsix` |
| CLI publish | `vsce publish` (or `vsce publish minor` / `vsce publish 0.1.0` to bump) |
| Web UI | `vsce package` then upload VSIX on [publisher management](https://marketplace.visualstudio.com/manage) |

SVG constraints: icon must not be SVG; README/CHANGELOG images must be `https`; SVGs only from approved badge providers. ([Publishing Extensions](https://code.visualstudio.com/api/working-with-extensions/publishing-extension))

### Listing requirements that commonly fail review / publish

Documented packaging and Marketplace presentation rules:

| Item | Requirement | Source |
| --- | --- | --- |
| Icon | PNG path via `icon`; **≥ 128×128** (256×256 for Retina); **not SVG** | [Manifest](https://code.visualstudio.com/api/references/extension-manifest); [Publishing](https://code.visualstudio.com/api/working-with-extensions/publishing-extension) |
| README | Root `README.md` becomes Marketplace body | [Manifest — Marketplace Presentation Tips](https://code.visualstudio.com/api/references/extension-manifest#marketplace-presentation-tips) |
| LICENSE | Root `LICENSE` file; `license` field in `package.json` | same |
| CHANGELOG | Root `CHANGELOG.md` recommended | same |
| Repository / bugs / homepage | Optional but shown under Resources; if `repository` points at public GitHub, vsce rewrites relative links | same |
| Categories | Only allowed list (e.g. Other, Programming Languages, …); Language Packs reserved | [Manifest fields](https://code.visualstudio.com/api/references/extension-manifest) |
| Keywords | Max **30** | FAQ on publishing page |
| Badges | Only approved badge URL prefixes | [Approved Badges](https://code.visualstudio.com/api/references/extension-manifest#approved-badges) |
| Privacy policy | Not a dedicated Marketplace form field in publish docs; Microsoft Marketplace Terms of Use apply. Extension runtime security docs describe malware/secret scanning, not a publisher privacy-policy URL requirement. | [Extension runtime security](https://code.visualstudio.com/docs/editor/extension-runtime-security); [Terms of Use PDF](https://cdn.vsassets.io/v/M190_20210811.1/_content/Microsoft-Visual-Studio-Marketplace-Terms-of-Use.pdf) |

Malware scan runs per publish/update; package stays unpublished until clear. Secret scanning can block publish. ([Extension runtime security](https://code.visualstudio.com/docs/editor/extension-runtime-security))

### Review / moderation timeline

- No fixed “X business days” human-review SLA for ordinary extension publish in the publish docs.
- **Verified publisher** domain validation: Marketplace team reviews and responds **within 5 business days** after TXT validation. Prerequisites: ≥ 6 months with extensions on Marketplace + domain registration ≥ 6 months. ([Verify a publisher](https://code.visualstudio.com/api/working-with-extensions/publishing-extension#verify-a-publisher))
- Support: Manage Publishers & Extensions → **Contact Microsoft**. ([Publishing FAQ](https://code.visualstudio.com/api/working-with-extensions/publishing-extension))

### Updating a version later

- Bump `version` (SemVer) and `vsce publish`, or `vsce publish patch|minor|major` / `vsce publish <version>` (updates `package.json`, and in a git repo may create version commit/tag via npm-version).
- Pre-release: `vsce publish --pre-release` (even/odd minor convention recommended; `engines.vscode` ≥ 1.63.0 for pre-release). ([Publishing Extensions](https://code.visualstudio.com/api/working-with-extensions/publishing-extension))

### CI publish and conventional secrets

Documented secret name: **`VSCE_PAT`**.

- Azure Pipelines: secret variable `VSCE_PAT` → `env: VSCE_PAT: $(VSCE_PAT)`.
- GitHub Actions: repository secret `VSCE_PAT` → `${{ secrets.VSCE_PAT }}`.
- GitLab CI: masked variable `VSCE_PAT`.

`vsce` reads `VSCE_PAT` by default when set. ([Continuous Integration — Automated publishing](https://code.visualstudio.com/api/working-with-extensions/continuous-integration#automated-publishing))

Entra/managed-identity path uses `vsce publish --azure-credential` instead of PAT (preferred before Dec 2026). ([Secure automated publishing](https://code.visualstudio.com/api/working-with-extensions/publishing-extension#secure-automated-publishing-to-visual-studio-marketplace))

---

## 2. Open VSX Registry (Cursor / VSCodium)

First-party ops wiki: [EclipseFdn/open-vsx.org — Publishing Extensions](https://github.com/EclipseFdn/open-vsx.org/wiki/Publishing-Extensions) (edited Feb 26, 2026 per wiki history; content accessed 2026-08-31). Registry: [https://open-vsx.org](https://open-vsx.org/). Managed by the Eclipse Foundation.

### Account / identity required

1. **Eclipse account** to sign the Open VSX **Publisher Agreement**: register at [https://accounts.eclipse.org/user/register](https://accounts.eclipse.org/user/register). Fill **GitHub Username** with the **same** GitHub account used on open-vsx.org.
2. Log in to [open-vsx.org](https://open-vsx.org) via **GitHub** (account icon → authorize).
3. Profile ([https://open-vsx.org/user-settings/profile](https://open-vsx.org/user-settings/profile)) → **Log in with Eclipse** → authorize → **Show Publisher Agreement** → read → **Agree**.
4. Note: Eclipse **Contributor Agreement (ECA)** is a *different* agreement (for contributing code to Eclipse projects), not a substitute for the Open VSX Publisher Agreement. ([Publishing Extensions wiki](https://github.com/EclipseFdn/open-vsx.org/wiki/Publishing-Extensions))

### Namespace / publisher rules (mostly irreversible in practice)

- Open VSX maps `package.json` `"publisher"` to a **namespace**.
- Valid namespace characters: letters, numbers, and `-`, `+`, `$`, `~` (server validator).
- Create via CLI before publish (if namespace ≠ GitHub ID):

  ```bash
  npx ovsx create-namespace <name> -p <token>
  ```

  For this repo: `npx ovsx create-namespace asjnaang -p <token>`.
- If create fails because the namespace exists, **you will not be able to use that namespace** (someone else already started the claim). ([Publishing Extensions](https://github.com/EclipseFdn/open-vsx.org/wiki/Publishing-Extensions); [Managing Namespaces](https://github.com/EclipseFdn/open-vsx.org/wiki/Managing-Namespaces))
- Creating a namespace grants **contributor**, **not** verified **owner**. Unverified listings show: *"That user account is not a verified publisher of the namespace"*.
- Ownership claim: GitHub issue on [EclipseFdn/open-vsx.org](https://github.com/EclipseFdn/open-vsx.org/issues) using the namespace template. Claimant GitHub ID needs **≥ 1 year** of history. ([Managing Namespaces](https://github.com/EclipseFdn/open-vsx.org/wiki/Managing-Namespaces))
- Rename/delete of namespaces is **admin-mediated** via issues; delete is not explicitly supported (admin rename/merge workaround). Treat `asjnaang` as effectively permanent once claimed.

### Access token (PAT)

1. [https://open-vsx.org/user-settings/tokens](https://open-vsx.org/user-settings/tokens) (avatar → Settings → Access Tokens).
2. **Generate New Token** + description (recommend one token per environment).
3. **Generate Token** → copy once; value is never shown again.
4. Pass with `-p <token>` or env (community/CI convention: **`OVSX_PAT`** — used in Eclipse Open VSX auto-publish examples). ([Auto Publishing Extensions](https://github.com/EclipseFdn/open-vsx.org/wiki/Auto-Publishing-Extensions) search snippets / wiki CI example)

Token scopes: not a multi-scope Azure-style matrix; token authorizes publishing for that user until deleted.

### Package / upload: CLI vs web UI

| Path | How |
| --- | --- |
| Package | Prefer **`vsce`** to produce `.vsix` (“Using other methods … is unreliable and is not supported”) |
| Web UI | Upper-right **Publish** → **Publish Extension** → select/drag `.vsix` ([Publishing Extensions](https://github.com/EclipseFdn/open-vsx.org/wiki/Publishing-Extensions)) |
| CLI | `npx ovsx publish <file.vsix> -p <token>` or `npx ovsx publish -p <token>` from extension root (uses vsce internally; add `--yarn` if Yarn scripts) |

Web publish under GitHub-matching namespace can create the namespace during publish; non-matching names need API/CLI create first. ([Managing Namespaces](https://github.com/EclipseFdn/open-vsx.org/wiki/Managing-Namespaces))

### Listing / scan checks that commonly fail

Automatic checks during publish ([Publishing Extensions](https://github.com/EclipseFdn/open-vsx.org/wiki/Publishing-Extensions)):

- **Secret detection** — rejects if secrets found (false positives: `// secret-detector:ignore` on line).
- **Blocklist** — known-bad file hashes.
- **Namespace similarity** — typosquatting protection.
- Suspected malware → rejection or quarantine (“under review”) until admin review; dispute via [EclipseFdn/open-vsx.org issues](https://github.com/EclipseFdn/open-vsx.org/issues).

Immediately after publish, extension may show **Deactivated** until async processing (typically ~5–10 seconds). No separate documented icon-size / HTML-description checklist like JetBrains; content still comes from the VSIX/`package.json`/README packaged by vsce.

Privacy policy: not called out as a dedicated Open VSX listing field in the publish wiki; Publisher Agreement acceptance is required.

### Review / moderation timeline

- Normal publish: automated scans + short async activation (seconds, longer if large/busy).
- Quarantine / malware path: human admin; no fixed SLA documented on the wiki page.
- Namespace ownership: human review of GitHub issue; timeline not stated on Managing Namespaces.

### Updating a version later

- Publish a new SemVer VSIX with `ovsx publish` (same as first publish). Same `publisher.name` identity.
- Nightly/auto mirror from VS Marketplace is a separate opt-in via `open-vsx/publish-extensions` (authors are told self-publish, e.g. GitHub Actions, is best). ([Auto Publishing Extensions](https://github.com/EclipseFdn/open-vsx.org/wiki/Auto-Publishing-Extensions))

### CI publish and conventional secrets

- Official wiki recommends publishing yourself (e.g. GitHub Actions) and points to [HaaLeo/publish-vscode-extension](https://github.com/HaaLeo/publish-vscode-extension).
- Example env from Eclipse Open VSX wiki auto-publish snippet: **`OVSX_PAT`**: `npx ovsx publish dist/*.vsix` with `env: OVSX_PAT: ${{ secrets.OVSX_PAT }}`.
- Dual Marketplace+Open VSX actions typically also use **`VSCE_PAT`**.

### Dual-publish: same publisher id?

**Yes — strongly required by Open VSX policy intent:**

> “If you publish your extension on by the VS Code Marketplace and the Open VSX Registry, it is our strong desire to have you use the **same identifier** between registries. I.e. **same extension name and same publisher account/namespace**.”  
> — [Publishing Extensions — Preserving Identity Across Registries](https://github.com/EclipseFdn/open-vsx.org/wiki/Publishing-Extensions)

If the Open VSX namespace matches a VS Code Marketplace publisher, ownership claims **must show write access** to that Marketplace publisher (GitHub org match, repo/commit proof, DNS TXT, or temporary reader access to Open VSX admin). ([Managing Namespaces](https://github.com/EclipseFdn/open-vsx.org/wiki/Managing-Namespaces))

For this repo: keep Open VSX namespace **`asjnaang`** aligned with Marketplace publisher **`asjnaang`**, extension name **`build-ai-context`**.

---

## 3. JetBrains Marketplace (IntelliJ Platform)

Primary docs:

- [Publishing a Plugin (SDK)](https://plugins.jetbrains.com/docs/intellij/publishing-plugin.html)
- [Uploading a new plugin](https://plugins.jetbrains.com/docs/marketplace/uploading-a-new-plugin.html)
- [Vendor profile](https://plugins.jetbrains.com/docs/marketplace/organizations.html)
- [Best practices for listing](https://plugins.jetbrains.com/docs/marketplace/best-practices-for-listing.html)
- [Plugin updates](https://plugins.jetbrains.com/docs/marketplace/plugin-updates.html)
- [Plugin upload API](https://plugins.jetbrains.com/docs/marketplace/plugin-upload.html)
- [Approval Guidelines](https://plugins.jetbrains.com/legal/approval-guidelines)
- [Plugin Logo](https://plugins.jetbrains.com/docs/intellij/plugin-icon-file.html)

### Account / identity required

1. **JetBrains Account**: [https://account.jetbrains.com](https://account.jetbrains.com) → Create Account → Register. ([Publishing a Plugin](https://plugins.jetbrains.com/docs/intellij/publishing-plugin.html#creating-a-jetbrains-account))
2. Log in to Marketplace author area: [https://plugins.jetbrains.com/author/me](https://plugins.jetbrains.com/author/me).
3. First upload requires accepting the [JetBrains Marketplace Developer Agreement](https://plugins.jetbrains.com/legal/developer-agreement) and creating a **Vendor** profile. ([Uploading a new plugin](https://plugins.jetbrains.com/docs/marketplace/uploading-a-new-plugin.html))
4. Upload entry points documented as: Profile → **Add new plugin**, or user menu → **Upload plugin** (both appear in official docs; UI may present both). New-plugin form also at [https://plugins.jetbrains.com/plugin/add#intellij](https://plugins.jetbrains.com/plugin/add#intellij) (linked from Vendor docs).

### Vendor ID rules (irreversible)

- Vendor is required for every plugin (individual or organization). ([Vendor profile](https://plugins.jetbrains.com/docs/marketplace/organizations.html))
- Create during first upload or via [https://plugins.jetbrains.com/organizations/new](https://plugins.jetbrains.com/organizations/new).
- **“Be sure to choose your Vendor ID carefully, because you won’t be able to edit this parameter later on.”** Public Vendor Name, Email, Website remain editable.
- Must declare **trader** vs **non-trader** (EU consumer rules) at creation.
- Plugin XML id for this repo: **`com.asjnaang.buildaicontext`** (distinct from Vendor ID; id lives in `plugin.xml` / Gradle). Vendor display name assumed **ASJN**.
- Free plugins can transfer between Vendors via UI; paid/freemium need Marketplace Support. ([Vendor profile](https://plugins.jetbrains.com/docs/marketplace/organizations.html))

### Permanent token (API / Gradle)

1. [My Tokens](https://plugins.jetbrains.com/author/me/tokens) in Marketplace profile.
2. Name the token → **Generate Token** → **copy before closing** (only shown once). ([Publishing a Plugin — Providing Your Personal Access Token](https://plugins.jetbrains.com/docs/intellij/publishing-plugin.html#providing-your-personal-access-token-to-gradle); [Plugin upload API](https://plugins.jetbrains.com/docs/marketplace/plugin-upload.html))

Gradle 2.x conventions:

- Property / env: `ORG_GRADLE_PROJECT_intellijPlatformPublishingToken` or `-PintellijPlatformPublishingToken=…`
- Extension docs: `intellijPlatform.publishing.token` **defaults to env `PUBLISH_TOKEN`**.
- Plugin Signing docs also show `PUBLISH_TOKEN` for `publishPlugin { token.set(...) }`.

API: `Authorization: Bearer <permanentToken>` to `https://plugins.jetbrains.com/api/updates/upload`.

### Package / upload: CLI vs web UI

| Step | How |
| --- | --- |
| Build ZIP | `./gradlew :plugin:buildPlugin` → `build/distributions` (or `signPlugin` if signing configured) |
| **First publication** | **Must be uploaded manually** on Marketplace ([Publishing a Plugin](https://plugins.jetbrains.com/docs/intellij/publishing-plugin.html)) |
| Later versions | Web **Upload Update**, or Gradle `publishPlugin`, or upload API |
| Max size | **400 MB** |

Signing: Marketplace signing recommended; `signPlugin` runs before `publishPlugin` when configured. ([Plugin Signing](https://plugins.jetbrains.com/docs/intellij/plugin-signing.html); publishing checklist)

### Listing requirements that commonly fail review

| Item | Requirement | Source |
| --- | --- | --- |
| Name | 1–4 words preferred (max 20 strongly recommended; hard max 60); no “Plugin”, no JetBrains product names, no emoji | [Best practices](https://plugins.jetbrains.com/docs/marketplace/best-practices-for-listing.html) |
| Description | From `plugin.xml` `<description>` (HTML); first **40 characters** English summary for cards; English first | same |
| Change notes | `change-notes` in `plugin.xml` → What’s New | same |
| Logo | Optional but if present: **`pluginIcon.svg`** (+ optional `pluginIcon_dark.svg`) in **`META-INF`**, **40×40** canvas, SVG only; do not use IntelliJ template default logo | [Plugin Logo](https://plugins.jetbrains.com/docs/intellij/plugin-icon-file.html); [Best practices — logo](https://plugins.jetbrains.com/docs/marketplace/best-practices-for-listing.html#plugin-logo) |
| Screenshots | After upload, Media section; **min recommended 1200×760**; theme plugins must show theme | [Best practices — Media](https://plugins.jetbrains.com/docs/marketplace/best-practices-for-listing.html) |
| License | **Mandatory** EULA/OSS license on upload; OSS requires **source code link** | [Uploading a new plugin](https://plugins.jetbrains.com/docs/marketplace/uploading-a-new-plugin.html); Approval Guidelines |
| Tags | At least one correct tag | Uploading docs |
| Privacy Notice | **Required if the plugin collects personal data** | [Approval Guidelines](https://plugins.jetbrains.com/legal/approval-guidelines) (Legal Agreements and Privacy) |
| Ads flag | Declare `containsAds` if commercial communications present | Upload API / upload form |
| Compatibility | Verified via Plugin Verifier; `since-build` / `until-build` | [Plugin updates](https://plugins.jetbrains.com/docs/marketplace/plugin-updates.html) |

Approval Guidelines also: accept Developer Agreement; trader/non-trader declaration. Full criteria: [https://plugins.jetbrains.com/legal/approval-guidelines](https://plugins.jetbrains.com/legal/approval-guidelines) (legal page; some fetchers return empty body when unauthenticated — open in browser).

### Review / moderation timeline

- Every new plugin **and every update** is manually reviewed before public availability. ([Approval Guidelines](https://plugins.jetbrains.com/legal/approval-guidelines); [Understanding plugin security](https://plugins.jetbrains.com/docs/marketplace/understanding-plugin-security.html))
- Approval Guidelines: JetBrains does **not guarantee** a timeframe; if no word within **3–4 working days**, email `marketplace@jetbrains.com`.
- Plugin updates doc: if no review-status notification within **2 business days**, contact `marketplace@jetbrains.com` or Marketplace forum. ([Plugin updates](https://plugins.jetbrains.com/docs/marketplace/plugin-updates.html))
- Paid release flow: review “within two business days” after sales details submission. ([Release the plugin](https://plugins.jetbrains.com/docs/marketplace/release-plugin.html))

### Updating a version later

1. Bump version (Marketplace rejects duplicate version artifacts).
2. Upload via UI (**Upload Update**), `./gradlew :plugin:publishPlugin`, or API.
3. Optional custom channel (`alpha` / `beta` / `eap` / arbitrary) or `isHidden` / `hidden` flag.
4. After approval, installed users are notified when update is verified. ([Publishing a Plugin](https://plugins.jetbrains.com/docs/intellij/publishing-plugin.html))

Cannot edit update contents after submission except compatibility range (`since-build` / `until-build`). ([Plugin updates](https://plugins.jetbrains.com/docs/marketplace/plugin-updates.html))

### CI publish and conventional secrets

- Supported after **one manual** first upload.
- Conventional secret / env names from JetBrains docs:
  - **`PUBLISH_TOKEN`** (default for `intellijPlatform.publishing.token` in Gradle Plugin 2.x)
  - **`intellijPlatformPublishingToken`** / `ORG_GRADLE_PROJECT_intellijPlatformPublishingToken`
  - Signing (if used): `CERTIFICATE_CHAIN`, `PRIVATE_KEY`, `PRIVATE_KEY_PASSWORD` ([Plugin Signing](https://plugins.jetbrains.com/docs/intellij/plugin-signing.html))

---

## Cross-marketplace checklist for this repo

| Decision | Value | Irreversible? |
| --- | --- | --- |
| VS Marketplace publisher ID | `asjnaang` | **Yes** (ID immutable) |
| Extension name | `build-ai-context` | Effectively yes if removed (name reserved) |
| Open VSX namespace | `asjnaang` (same as publisher) | Create-once; ownership via GitHub issue; rename only via admin |
| JetBrains Vendor ID | choose carefully at first upload | **Yes** (cannot edit later) |
| JetBrains plugin XML id | `com.asjnaang.buildaicontext` | Treat as permanent identity for the listing |

**Suggested human order:**

1. Microsoft account + Azure DevOps org → PAT (Marketplace Manage) → create publisher `asjnaang` → `vsce login` → package/publish `build-ai-context`.
2. Eclipse account (GitHub username linked) + open-vsx.org GitHub login → Publisher Agreement → token → `ovsx create-namespace asjnaang` → publish same VSIX → claim namespace ownership (prove Marketplace write access).
3. JetBrains Account → Vendor (ASJN / chosen Vendor ID) + trader declaration + Developer Agreement → manual first upload of `buildPlugin` ZIP → later `publishPlugin` with `PUBLISH_TOKEN`.

---

## Source index (access date 2026-08-31)

1. https://code.visualstudio.com/api/working-with-extensions/publishing-extension  
2. https://code.visualstudio.com/api/references/extension-manifest  
3. https://code.visualstudio.com/api/working-with-extensions/continuous-integration  
4. https://code.visualstudio.com/docs/editor/extension-runtime-security  
5. https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/create-organization  
6. https://marketplace.visualstudio.com/manage  
7. https://github.com/EclipseFdn/open-vsx.org/wiki/Publishing-Extensions  
8. https://github.com/EclipseFdn/open-vsx.org/wiki/Managing-Namespaces  
9. https://github.com/EclipseFdn/open-vsx.org/wiki/Auto-Publishing-Extensions  
10. https://open-vsx.org/user-settings/profile · https://open-vsx.org/user-settings/tokens  
11. https://accounts.eclipse.org/user/register  
12. https://plugins.jetbrains.com/docs/intellij/publishing-plugin.html  
13. https://plugins.jetbrains.com/docs/marketplace/uploading-a-new-plugin.html  
14. https://plugins.jetbrains.com/docs/marketplace/organizations.html  
15. https://plugins.jetbrains.com/docs/marketplace/best-practices-for-listing.html  
16. https://plugins.jetbrains.com/docs/marketplace/plugin-updates.html  
17. https://plugins.jetbrains.com/docs/marketplace/plugin-upload.html  
18. https://plugins.jetbrains.com/docs/intellij/plugin-icon-file.html  
19. https://plugins.jetbrains.com/docs/intellij/plugin-signing.html  
20. https://plugins.jetbrains.com/docs/intellij/tools-intellij-platform-gradle-plugin-extension.html (publishing.token → `PUBLISH_TOKEN`)  
21. https://plugins.jetbrains.com/legal/approval-guidelines  
22. https://account.jetbrains.com · https://plugins.jetbrains.com/author/me · https://plugins.jetbrains.com/author/me/tokens  

Pages that may require login for full content: Marketplace manage UIs, open-vsx.org settings, JetBrains author/tokens, and portions of JetBrains legal HTML when fetched programmatically.
