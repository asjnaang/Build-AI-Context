# build-ai-context

Export source code and project files into AI-friendly text bundles with a compact manifest.

**Commands:** `build-ai-context` or `baic` (short alias)

## Features

- **Multi-language support**: Python, TypeScript, JavaScript, Java, Kotlin, Swift, HTML/CSS, and more
- **AI-optimized output**: Creates bundle files with embedded metadata for AI assistants
- **Smart filtering**: Respects `.gitignore` and skips build/cache directories automatically
- **Manifest generation**: Produces `MANIFEST.json` with precise file location mappings
- **Project overview**: Optional `PROJECT_OVERVIEW.txt` for architecture insights
- **Secret protection**: Skips `.env`, keys, certificates, and other sensitive files by default
- **Fancy interactive UI**: Checkbox-style selection with questionary
- **Large file handling**: Automatically splits large files into manageable chunks

## Installation

```bash
pip install build-ai-context
```

## Quick Start

### CLI Usage

```bash
# Show version
build-ai-context --version
baic --version

# Interactive mode - scan current directory
build-ai-context
baic

# Specify project root
build-ai-context /path/to/project
baic /path/to/project

# Non-interactive mode with specific categories
build-ai-context /path/to/project --non-interactive --categories python typescript
baic /path/to/project --non-interactive --categories python typescript

# Export specific files or folders
build-ai-context . --non-interactive --paths src main.py
baic . --non-interactive --paths src main.py

# Generate project overview
build-ai-context . --project-overview
baic . --project-overview

# Use fancy interactive UI
build-ai-context . --fancy-ui
baic . --fancy-ui

# Set custom output directory
build-ai-context . --output-dir ./my-bundles
baic . --output-dir ./my-bundles

# Adjust max lines per bundle
build-ai-context . --max-lines 10000
baic . --max-lines 10000

# Include secret files (use with caution)
build-ai-context . --include-secret-files
baic . --include-secret-files
```

## Output Files

After running, you'll get:

| File | Description |
|------|-------------|
| `bundle_001.txt`, `bundle_002.txt`, ... | Text bundles containing your source code |
| `MANIFEST.json` | Maps files to bundles and line ranges |
| `README_EXPORT.txt` | Summary of the export |
| `PROJECT_OVERVIEW.txt` | (Optional) Architecture overview |

## Categories

| Category | Description | Extensions |
|----------|-------------|------------|
| `python` | Python backend / scripts | `.py` |
| `typescript` | TypeScript / TSX | `.ts`, `.tsx` |
| `javascript` | JavaScript / JSX | `.js`, `.jsx`, `.mjs`, `.cjs` |
| `java_kotlin` | Android / JVM | `.java`, `.kt`, `.kts`, `.gradle` |
| `ios_apple` | iOS / Apple platform | `.swift`, `.m`, `.h`, etc. |
| `web_ui` | HTML / CSS / UI | `.html`, `.css`, `.scss`, `.vue`, etc. |
| `config_docs` | Config / metadata | `.json`, `.yaml`, `.xml`, `.toml`, `.md` |

### Category Aliases

| Alias | Maps to |
|-------|---------|
| `py` | `python` |
| `ts`, `tsx` | `typescript` |
| `js`, `jsx` | `javascript` |
| `java`, `kotlin`, `android` | `java_kotlin` |
| `ios`, `swift`, `apple` | `ios_apple` |
| `web`, `frontend`, `ui` | `web_ui` |
| `config`, `docs` | `config_docs` |

## Usage Examples

### Export Python and TypeScript code for AI review

```bash
baic /my-project --non-interactive --categories python typescript --project-overview
```

### Export specific folders

```bash
baic . --non-interactive --paths src/components src/utils
```

### Full export with all features

```bash
baic /path/to/project \
    --non-interactive \
    --categories python typescript web_ui \
    --max-lines 10000 \
    --project-overview \
    --output-dir ./ai-review-bundles
```

### Interactive mode with fancy UI

```bash
baic . --fancy-ui
```

### Use with AI assistants

After running the exporter:

1. **Attach bundles**: Upload `bundle_001.txt` (and others) to your AI assistant
2. **Include manifest**: Upload `MANIFEST.json` so the assistant understands file mappings
3. **Add overview**: Upload `PROJECT_OVERVIEW.txt` for architecture context
4. **Ask questions**: The assistant can now reference exact file locations and line numbers

## Security

By default, the following files are **skipped** to protect sensitive data:

- `.env` files and variants (`*.env.*`)
- Private keys (`*.pem`, `*.key`, `id_rsa`, `id_ed25519`)
- Certificates (`*.crt`, `*.cer`, `*.der`)
- Keystores (`*.jks`, `*.keystore`, `*.p12`, `*.pfx`)
- Mobile provisioning (`*.mobileprovision`)
- Firebase/Google config (`google-services.json`, `GoogleService-Info.plist`)

Use `--include-secret-files` to override this behavior (use with caution).

## CLI Options

```
usage: build-ai-context [-h] [--max-lines MAX_LINES] [--output-dir OUTPUT_DIR]
                        [--non-interactive] [--categories [CATEGORIES ...]]
                        [--paths [PATHS ...]] [--include-secret-files]
                        [--fancy-ui] [--project-overview] [--version]
                        [project_root]

positional arguments:
  project_root          Project root to scan (default: current directory)

options:
  -h, --help            Show help message
  --version             Show version
  --max-lines N         Max lines per bundle (default: 8000)
  --output-dir DIR      Custom output directory
  --non-interactive     Run without prompts
  --categories CATS     Categories to export (e.g., python typescript)
  --paths PATHS         Specific files/folders to export
  --include-secret-files Include secret-like files
  --fancy-ui            Use checkbox-style interactive UI
  --project-overview    Generate PROJECT_OVERVIEW.txt
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details.
