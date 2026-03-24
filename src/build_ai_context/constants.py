"""
Constants and configuration for build_ai_context package.
"""

from typing import Dict, Set

# Default configuration values
DEFAULT_MAX_LINES: int = 8000
DEFAULT_OUTPUT_DIR: str = "exported_sources"
DEFAULT_TEXT_ENCODING: str = "utf-8"

# Category extensions mapping
CATEGORY_EXTENSIONS: Dict[str, Set[str]] = {
    "python": {".py"},
    "typescript": {".ts", ".tsx"},
    "javascript": {".js", ".jsx", ".mjs", ".cjs"},
    "java_kotlin": {".java", ".kt", ".kts", ".gradle", ".properties", ".pro"},
    "ios_apple": {".swift", ".m", ".mm", ".h", ".hpp", ".pbxproj", ".plist", ".xcconfig"},
    "web_ui": {".html", ".css", ".scss", ".sass", ".less", ".vue", ".svelte"},
    "shell": {".sh", ".bash", ".zsh"},
    "config_docs": {".json", ".yaml", ".yml", ".xml", ".toml", ".graphql", ".gql", ".md", ".txt"},
}

# Special filenames that should be included
SPECIAL_FILENAMES: Set[str] = {
    "Dockerfile",
    "Podfile",
    "Gemfile",
    "Fastfile",
    "Makefile",
    "Jenkinsfile",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "tsconfig.json",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-ci.txt",
    "Pipfile",
    "Pipfile.lock",
    ".swiftlint.yml",
    ".eslintrc",
    ".eslintrc.json",
    ".eslintrc.js",
    ".prettierrc",
    ".prettierrc.json",
    ".prettierrc.js",
    "AndroidManifest.xml",
    "gradle.properties",
    "settings.gradle",
    "settings.gradle.kts",
    "build.gradle",
    "build.gradle.kts",
}

# Directories to always skip
DEFAULT_EXCLUDED_DIRS: Set[str] = {
    ".git",
    ".svn",
    ".hg",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".nuxt",
    ".turbo",
    "coverage",
    ".coverage",
    ".gradle",
    ".kotlin",
    "Pods",
    "DerivedData",
    ".dart_tool",
    ".serverless",
    ".terraform",
    ".expo",
    ".parcel-cache",
    ".yarn",
    ".pnpm-store",
    ".cache",
    "out",
    "bin",
    "obj",
    "target",
    ".github",
}

# Directory prefixes to always skip (paths starting with these)
DEFAULT_EXCLUDED_PREFIXES: Set[str] = {
    "exported_sources",
}

# Extra file patterns to skip (not in .gitignore but not needed for context)
EXTRA_EXCLUDED_PATTERNS: Set[str] = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lockb",
    "*.lock",
    ".DS_Store",
    "thumbs.db",
    "*.swp",
    "*.swo",
    "*~",
    ".DS_Store",
}

# Secret-like file patterns to skip by default
DEFAULT_SECRET_PATTERNS: Set[str] = {
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.crt",
    "*.cer",
    "*.p12",
    "*.pfx",
    "*.jks",
    "*.keystore",
    "*.mobileprovision",
    "*.der",
    "*.p8",
    "id_rsa",
    "id_ed25519",
    "google-services.json",
    "GoogleService-Info.plist",
}

# Category descriptions for display
CATEGORY_DESCRIPTIONS: Dict[str, str] = {
    "python": "Python backend / scripts",
    "typescript": "TypeScript / TSX",
    "javascript": "JavaScript / JSX",
    "java_kotlin": "Android / JVM (Java, Kotlin, Gradle, properties)",
    "ios_apple": "iOS / Apple platform files",
    "web_ui": "HTML / CSS / UI frameworks",
    "shell": "Shell scripts (bash, zsh)",
    "config_docs": "Config / metadata / docs",
}

# Category aliases for user input
CATEGORY_ALIASES: Dict[str, str] = {
    "py": "python",
    "python": "python",
    "ts": "typescript",
    "tsx": "typescript",
    "typescript": "typescript",
    "js": "javascript",
    "jsx": "javascript",
    "javascript": "javascript",
    "java": "java_kotlin",
    "kotlin": "java_kotlin",
    "android": "java_kotlin",
    "jvm": "java_kotlin",
    "ios": "ios_apple",
    "swift": "ios_apple",
    "apple": "ios_apple",
    "web": "web_ui",
    "frontend": "web_ui",
    "ui": "web_ui",
    "shell": "shell",
    "bash": "shell",
    "zsh": "shell",
    "sh": "shell",
    "config": "config_docs",
    "docs": "config_docs",
}

# Files to check for framework detection
INTERESTING_FILES: Set[str] = {
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-ci.txt",
    "Pipfile",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "tsconfig.json",
    "Podfile",
    "Gemfile",
    "Fastfile",
    "Makefile",
    "Dockerfile",
    "Jenkinsfile",
    "AndroidManifest.xml",
    "gradle.properties",
    "settings.gradle",
    "settings.gradle.kts",
    "build.gradle",
    "build.gradle.kts",
}
