# build-ai-context

Export selected source and project files as readable text bundles or a Base64-encoded compressed text payload with a compact manifest and agent prompt. Perfect for feeding your codebase to AI assistants like Claude, GPT-4, Copilot, or any LLM.

**Commands:** `build-ai-context` or `baic` (short alias)

## Why use this?

- **AI-Ready Output**: Bundles include metadata (file paths, line numbers, categories) so AI can precisely reference your code
- **Smart Filtering**: Automatically skips build artifacts, dependencies, secrets, and previously exported bundles
- **Flexible Selection**: 5 ways to select files - export everything, by category, by path, mixed, or by keywords in code
- **Continuous Workflow**: Stay in the tool - export, then export more files without restarting

## Quick Start

```bash
# Install
pip install build-ai-context

# Interactive mode (recommended for first use)
baic

# Non-interactive - export everything supported
baic . --all

# Non-interactive - export specific categories
baic . --non-interactive --categories python typescript
```

## Installation

```bash
pip install build-ai-context
```

Or for development:

```bash
git clone https://github.com/asjnaang/build-ai-context
cd build-ai-context
pip install -e .
```

## Interactive Mode (5 Ways to Select Files)

When you run `baic` without flags, you'll see an interactive menu. Choose how to select files:

### 1) all - Export Everything Supported
Export all supported files in your project. Simple and complete.

### 2) category - Pick by Language/Type
Select specific categories like `python`, `typescript`, `java_kotlin`, `shell`, etc.

```bash
# In interactive mode, choose option 2, then enter:
python,shell,config_docs
```

### 3) path - Pick Files/Folders by Path
Specify exact paths, filenames, or folder names:

```bash
# Non-interactive - handles spaces intelligently
baic . --non-interactive --paths src app tests

# Mixed commas and spaces work too
baic . --non-interactive --paths "main.py utils.py, helpers.py"
```

The tool intelligently parses paths even if you mix commas and spaces or omit separators.

### 4) mixed - Categories + Paths + Name Filters
Combine categories, paths, and filename filters:

```bash
# Select python files in src folder containing "auth" or "login"
# In interactive mode: choose 4, then enter categories, paths, and filters
```

### 5) keyword - Search Code Content
Search for keywords in your actual code and export files containing them:

```bash
# Non-interactive
baic . --non-interactive --keywords TODO FIXME,BUG,HACK

# Interactive - great for finding:
# - TODO/FIXME comments
# - Function names (e.g., "authenticate", "validate")
# - Error handling patterns
```

In interactive mode, you'll see a checkbox UI with all matching files pre-selected. Uncheck any files you don't want, then press Enter to bundle.

## CLI Options

| Option | Description | Example |
|--------|-------------|---------|
| `project_root` | Directory to scan (default: current) | `baic /path/to/project` |
| `--tree` | Generate filetree only, exit | `baic --tree .` |
| `--graph` | Generate code graph only (catalog + imports), exit | `baic --graph .` |
| `--format` | Graph file format: `txt` (default) or `json` | `--graph --format json` |
| `--categories` | Export by category | `--categories python typescript` |
| `--paths` | Export by path/filename | `--paths src tests` |
| `--keywords` | Search in code content | `--keywords TODO FIXME` |
| `--exclude-paths` | Remove files/folders from the final selected set | `--exclude-paths tests fixtures` |
| `--exclude-formats` | Remove file extensions from the final selected set | `--exclude-formats .json *.md` |
| `--task` | Replace the generated prompt's Task Contract placeholder | `--task "Fix the reported issue"` |
| `--task-clipboard`, `--tc` | Read the Task Contract from the macOS clipboard | `--tc` |
| `--non-interactive` | Run without prompts | `--non-interactive` |
| `--all` | Export everything supported without prompts | `baic . --all` |
| `--max-file-lines` | Skip repo source files with ≥ N lines when bundling (default: 3000; `0` = no limit). Bundle output size stays fixed at 8000 lines. | `--max-file-lines 10000` |
| `--force-ignored` | Include supported files under explicit `--paths` even when ignored; secret-like files still require `--include-secret-files` | `--paths .gen_files/reports --force-ignored` |
| `--force-bundle` | Bundle selected files regardless of the per-file line limit; oversized JSON is sampled when possible | `--paths reports --force-bundle` |
| `--transport` | `tar-gz` (default) or readable `text` bundles | `--transport text` |
| `--binary-policy` | `include` (default), `skip`, or `compressed-only` | `--binary-policy compressed-only` |
| `--output-dir` | Custom output folder | `--output-dir ./my-bundles` |
| `--project-overview` | Generate architecture overview | `--project-overview` |
| `--include-secret-files` | Include .env, keys, etc. (careful!) | `--include-secret-files` |
| `--redact` | Redact secrets from output | `--redact` |
| `--version` | Show version | `--version` |

## Categories Supported

| Category | Extensions |
|----------|------------|
| `python` | `.py` |
| `typescript` | `.ts`, `.tsx` |
| `javascript` | `.js`, `.jsx`, `.mjs`, `.cjs` |
| `java_kotlin` | `.java`, `.kt`, `.kts`, `.gradle` |
| `ios_apple` | `.swift`, `.m`, `.h`, `.plist` |
| `web_ui` | `.html`, `.css`, `.scss`, `.vue`, `.svelte` |
| `shell` | `.sh`, `.bash`, `.zsh` |
| `flutter` | `.dart` |
| `config_docs` | `.json`, `.jsonl`, `.yaml`, `.toml`, `.md`, `.txt`, `.log`, `.sql`, `.csv` |

`.log` and `.jsonl` files are supported as config/docs. Files ignored by `.gitignore` remain
excluded by default; include a specific ignored path with `--paths <path> --force-ignored`.

### Category Aliases

Shortcuts you can use: `py`→`python`, `ts`→`typescript`, `js`→`javascript`, `android`→`java_kotlin`, `ios`→`ios_apple`, `web`→`web_ui`, `sh`→`shell`, `dart`→`flutter`

## Output Files

The default `tar-gz` transport keeps the generated package within the three-attachment workflow: one payload text file, one manifest, and one `baic_prompt.md`. The optional `text` transport preserves the readable framed-bundle behavior: BAIC writes readable, framed
`*_bundle_*.txt` files capped at 8000 rendered lines, one manifest JSON, and the single `baic_prompt.md`.

Use `--transport tar-gz` when attachment count matters. BAIC deterministically TARs and Gzip-compresses the
selected exact source bytes, Base64-encodes the archive, and writes one `*_payload_*.txt` attachment instead of
a binary archive. The output is one payload text file, one manifest JSON, and the single `baic_prompt.md`. The
manifest validates the payload, Base64 body, decoded archive, and every source entry.

Examples:

```bash
# Existing commands remain readable text bundles.
baic . --all
baic . --non-interactive --paths src tests

# One compressed text payload for agents that reject binary archive attachments.
baic . --all --transport tar-gz
```

Redaction remains available with the optional `text` transport; `--redact` cannot be combined with `--transport tar-gz` because compressed transport preserves exact selected bytes. `tar-gz` is an internal archive representation;
no `.tar.gz`, `.gz`, or `.zip` attachment remains in the generated output directory.

PDF files are binary. With `--transport text`, BAIC wraps their original bytes as Base64 in the readable
bundle, just as it does for `.gz` files; the manifest records `encoding: base64`, the original byte size,
and the original SHA-256. With `--transport tar-gz`, the PDF is stored byte-for-byte in the internal TAR
before the payload is Gzip-compressed and Base64-encoded. PDFs larger than 15 MiB are called out in the
manifest warnings and in the completion output. Because most PDFs already compress their streams, Gzip may
not reduce their size significantly.

Use `--binary-policy include` to retain supported binary files in either transport, `skip` to omit them, or
`compressed-only` to omit them from readable text bundles while retaining them with `--transport tar-gz`.
BAIC never silently changes transport. The manifest records selected files, transported files, policy omissions,
and their counts separately so downstream agents can distinguish user selection from delivered source.

Format behavior is defined centrally in `src/build_ai_context/formats.py`. Add future binary formats there instead
of duplicating scanner, line-limit, redaction, transport, and warning conditions across modules. Export planning is
transport-neutral; renderers consume an explicit plan rather than inferring compressed archive membership from
text-bundle chunks.

## Filetree Feature

Generate a path list that AI agents can parse: one full relative path per line, each ending with a comma:

```bash
# Generate filetree only (quick project overview)
baic --tree .
baic --tree /path/to/project

# Filetree is automatically included in exports
baic . --non-interactive
```

Example filetree output:
```
root: myproject
file_count: 4

paths:
README.md,
main.py,
src/app.kt,
src/config.xml,

types:
config_docs: 2
java_kotlin: 1
python: 1
```

## Code graph

`baic --graph` writes a small map of the repo for AI agents: a per-file catalog of defs, plus import edges. Same flag style as `--tree`. One scan, then exit.

```bash
# Graph only (txt by default)
baic --graph .
baic --graph /path/to/project

# Same facts as JSON
baic --graph --format json .

# Tree + graph, one scan
baic --tree --graph .
```

Python is parsed with the stdlib `ast` module. TypeScript/JavaScript, Kotlin, Swift, Java, and Dart use tree-sitter when `build-ai-context[graph]` is installed (`pip install 'build-ai-context[graph]'`, Python 3.10+). Without that extra, those languages still get a heuristic catalog + imports so `--graph` never requires a native wheel.

Example:

```
root: myproject
file_count: 4
parsed: 3
skipped: 1
engine: ast, tree-sitter
languages: python=2, typescript=1

catalog:
src/cli.py:
  rank: 0.4120,
  fn: main @12,
  fn: run_exporter @40,
src/models.py:
  rank: 0.1881,
  class: SourceFile @14,

imports:
src/cli.py --> src/exporter.py,
src/cli.py --> src/models.py,
```

Catalog files are ordered by PageRank on local import edges (same idea as Aider's repo map): hubs other files import show up first. Each def includes its line so an agent can jump there. `--format json` is the same payload for tools.

This is not a full call graph. Local imports are resolved to project files when we can; third-party / stdlib names stay as module strings.

## Redaction

By default, redaction is **disabled** to preserve code integrity. Enable it when sharing with external parties:

```bash
# Without redaction (default) - code stays intact
baic . --non-interactive

# With redaction - secrets are replaced with <REDACTED>
baic . --non-interactive --redact
```

Redaction targets: API keys, tokens, passwords, JWTs, AWS keys, GitHub tokens, etc.

## What Gets Excluded

### Automatically Skipped (No config needed)

- **Directories**: `.git`, `node_modules`, `__pycache__`, `.gradle`, `build`, `dist`, `target`, `.github`
- **Generated outputs**: `.gen_files` folders, plus legacy `exported_sources*` folders for backward compatibility
- **Lock files**: `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`
- **System files**: `.DS_Store`, `thumbs.db`, `*.swp`

### Large Files

Line thresholds apply only to textual source formats. Base64 is a transport representation, so binary formats are
controlled by `--binary-policy` and byte-size warnings rather than by encoded line count.

- **>= 1500 lines**: Exported and reported under manifest `warnings`
- **>= 3000 lines**: Excluded by default; interactive mode lets you select files to include anyway

Use `--force-bundle` to disable the per-file line limit for selected files. For oversized JSON, the exporter samples the document when retaining its
schema and representative values is more useful than skipping them. The exporter
retains up to five representatives per structural shape, reducing to a minimum of
three when necessary. Sampling is in memory and never rewrites source files.

```bash
baic . --non-interactive --paths data --force-bundle

# Include an explicitly requested generated/ignored directory
baic . --non-interactive --paths .gen_files/git_commit_exports/run \
    --force-ignored --force-bundle
```

### Secrets (Skipped by default, include with `--include-secret-files`)

- `.env` files and variants
- Private keys (`*.pem`, `*.key`, `id_rsa`)
- Certificates, keystores, Firebase configs

## Usage Examples

### Export Python code for Claude/GPT review

```bash
baic /my-project --non-interactive --categories python --project-overview
```

### Find all files with TODO comments

```bash
# Interactive
baic
# Choose option 5, enter: TODO

# Or non-interactive
baic . --non-interactive --keywords TODO
```

### Export specific folders

```bash
baic . --non-interactive --paths src/components src/utils
```

### Exclude paths or file formats from a selection

Exclusions run after categories, paths, or keyword selection and immediately before bundling.
They do not change the project-wide filetree, which still describes all scanned supported files.

```bash
# Include src and tests, then remove fixtures and all JSON/Markdown files
baic . --non-interactive --paths src tests \
    --exclude-paths tests/fixtures \
    --exclude-formats .json md
```

`--exclude-paths` accepts the same relative paths, absolute paths, filenames, folders, commas,
and multiline input as `--paths`. `--exclude-formats` accepts `json`, `.json`, or `*.json`.

### Include the task in the generated AI prompt

```bash
baic . --non-interactive --paths src/components src/utils \
    --task "Review these files and fix the issues we discussed."
```

The task replaces the placeholder under `## Task` in the transport-specific source template. Both transports
still generate the same attachment name, `baic_prompt.md`: `tar-gz` uses `baic_prompt_gzip.md`, while `text`
uses `baic_prompt_text.md`. This preserves transport-correct extraction instructions without increasing the
number of generated attachments. Omit `--task` to keep the placeholder.

For long multiline tasks, JSON, quotes, or other shell-sensitive content, copy the
complete task and use `--tc` (or `--task-clipboard`). The CLI reads the clipboard
internally, so the content is not parsed by the shell:

```bash
baic . --non-interactive --paths src/components src/utils --tc
```

Simple aliases are sufficient:

```zsh
alias baicp='baic . --non-interactive --paths'
alias baick='baic . --non-interactive --keywords'
alias baica='baic . --all'
```

### Full export with overview

```bash
baic /path/to/project \
    --non-interactive \
    --categories python typescript web_ui \
    --max-file-lines 10000 \
    --project-overview \
    --output-dir ./ai-review-bundles
```

### Stay in the tool for multiple exports

```bash
baic
# Export python files...
# When asked "Do you want to export more files?" answer Y
# Export shell scripts...
# Answer N to exit
```

## Using with AI Assistants

1. **Run the exporter**: `baic . --categories python`
2. **Upload the generated text**: Attach readable bundle files, or the single payload text file produced by `--transport tar-gz`.
3. **Upload the manifest and prompt**: Attach the manifest and the generated `baic_prompt.md`.
4. **Ask away**: The AI validates and extracts exact repository files before working.

Example prompt to AI:
> "I've uploaded my Python project. Using the MANIFEST.json, find the authentication logic in src/auth.py and help me add password reset functionality."

## CLI Reference

```
usage: build-ai-context [-h] [--max-file-lines N] [--output-dir OUTPUT_DIR]
                       [--non-interactive] [--categories [CATEGORIES ...]]
                       [--paths [PATHS ...]] [--keywords [KEYWORDS ...]]
                       [--exclude-paths [EXCLUDE_PATHS ...]]
                       [--exclude-formats [EXCLUDE_FORMATS ...]]
                       [--task TASK | --task-clipboard] [--force-ignored] [--force-bundle]
                       [--include-secret-files] [--project-overview]
                       [--tree] [--graph] [--format {txt,json}] [--redact] [--version]
                       [project_root]

positional arguments:
  project_root          Project root to scan (default: current directory)

options:
  -h, --help            Show help message
  --version             Show version
  --tree                Generate filetree only and exit
  --graph               Generate code graph (catalog + imports) and exit
  --format {txt,json}   Graph file format (default: txt)
  --redact              Redact secrets from output (default: disabled)
  --max-file-lines N    Skip repo source files with >= N lines (default: 3000;
                        0 disables the per-file limit). Output bundles are
                        always packed to 8000 lines max.
  --force-ignored       Include ignored files under explicit --paths
  --force-bundle        Bundle selected files without the per-file line limit
  --output-dir DIR      Custom output directory
  --non-interactive     Run without prompts
  --categories CATS     Categories to export
  --paths PATHS         Files/folders to export
  --keywords KEYWORDS   Keywords to search in file content
  --exclude-paths PATHS Remove files/folders from the final selected set
  --exclude-formats EXT Remove extensions from the final selected set
  --task TASK            Replace the Task placeholder in the transport-specific prompt
  --task-clipboard, --tc Read the Task Contract from the macOS clipboard
  --include-secret-files Include secret-like files
  --project-overview    Generate PROJECT_OVERVIEW.txt
```

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details.
