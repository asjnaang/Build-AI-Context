# build-ai-context

Export source code and project files into AI-friendly text bundles with a compact manifest. Perfect for feeding your codebase to AI assistants like Claude, GPT-4, Copilot, or any LLM.

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
| `--categories` | Export by category | `--categories python typescript` |
| `--paths` | Export by path/filename | `--paths src tests` |
| `--keywords` | Search in code content | `--keywords TODO FIXME` |
| `--non-interactive` | Run without prompts | `--non-interactive` |
| `--max-lines` | Lines per bundle (default: 8000) | `--max-lines 10000` |
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
| `config_docs` | `.json`, `.yaml`, `.toml`, `.md` |

### Category Aliases

Shortcuts you can use: `py`→`python`, `ts`→`typescript`, `js`→`javascript`, `android`→`java_kotlin`, `ios`→`ios_apple`, `web`→`web_ui`, `sh`→`shell`, `dart`→`flutter`

## Output Files

After running, you'll get:

| File | Description |
|------|-------------|
| `<project>_bundle_001_<timestamp>.txt`, ... | Text bundles with consistent timestamps |
| `<project>_manifest_<timestamp>.json` | Maps every file to its bundle and line numbers |
| `<project>_readme_<timestamp>.txt` | Quick summary of what was exported |
| `<project>_file_tree_<timestamp>.txt` | Filetree with icons and type summary |
| `PROJECT_OVERVIEW.txt` | (with `--project-overview`) Architecture overview |

### Bundle Format

Each file in a bundle includes a header that AI assistants can use to locate code:

```
# ===== BEGIN FILE: src/utils/auth.py =====
# category : python
# chunk : 1/1
# line_range : 1-50
# total_lines : 50
# ===== CONTENT =====
def authenticate(user):
    ...
# ===== END FILE: src/utils/auth.py (chunk 1/1) =====
```

### MANIFEST.json Structure

```json
{
  "tool": "build-ai-context",
  "selected_files": ["src/main.py", "src/utils.py"],
  "selection": {
    "selection_mode": "category",
    "selected_categories": ["python"],
    "selected_paths": []
  },
  "bundles": [
    {
      "bundle": "bundle_001.txt",
      "files": [
        {
          "path": "src/main.py",
          "category": "python",
          "file_start_line": 1,
          "file_end_line": 50,
          "bundle_start_line": 10,
          "bundle_end_line": 59
        }
      ]
    }
  ]
}
```

## Filetree Feature

Generate a visual filetree with file type icons and summary statistics:

```bash
# Generate filetree only (quick project overview)
baic --tree .
baic --tree /path/to/project

# Filetree is automatically included in exports
baic . --non-interactive
```

Example filetree output:
```
myproject/
├── 🐍 main.py
├── 📕 README.md
├── src/
│   ├── 🟪 app.kt
│   └── 📄 config.xml
...

📊 File Summary:
  🟪 Kotlin       × 15
  📕 Markdown     × 3
  🐍 Python       × 2
  📄 XML          × 1
  ───
  📁  Total: 21 files
```

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
- **Exported bundles**: `exported_sources*` folders (prevents re-bundling previous exports)
- **Lock files**: `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`
- **System files**: `.DS_Store`, `thumbs.db`, `*.swp`

### Large Files

- **>= 1500 lines**: Exported with a warning (may need cleanup)
- **>= 3000 lines**: Skipped automatically (shown separately for manual handling)

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

### Full export with overview

```bash
baic /path/to/project \
    --non-interactive \
    --categories python typescript web_ui \
    --max-lines 10000 \
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
2. **Upload bundles**: Attach `bundle_001.txt`, `bundle_002.txt`, etc.
3. **Upload manifest**: Attach `MANIFEST.json` so AI understands file mappings
4. **Ask away**: The AI can now reference exact file paths and line numbers

Example prompt to AI:
> "I've uploaded my Python project. Using the MANIFEST.json, find the authentication logic in src/auth.py and help me add password reset functionality."

## CLI Reference

```
usage: build-ai-context [-h] [--max-lines MAX_LINES] [--output-dir OUTPUT_DIR]
                       [--non-interactive] [--categories [CATEGORIES ...]]
                       [--paths [PATHS ...]] [--keywords [KEYWORDS ...]]
                       [--include-secret-files] [--project-overview]
                       [--tree] [--redact] [--version]
                       [project_root]

positional arguments:
  project_root          Project root to scan (default: current directory)

options:
  -h, --help            Show help message
  --version             Show version
  --tree                Generate filetree only and exit
  --redact              Redact secrets from output (default: disabled)
  --max-lines N         Max lines per bundle (default: 8000)
  --output-dir DIR      Custom output directory
  --non-interactive     Run without prompts
  --categories CATS     Categories to export
  --paths PATHS         Files/folders to export
  --keywords KEYWORDS   Keywords to search in file content
  --include-secret-files Include secret-like files
  --project-overview    Generate PROJECT_OVERVIEW.txt
```

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details.
