"""
Icon constants for filetree generation.

Uses Unicode emojis that visually represent file types in text output.
"""

from typing import Dict, Tuple
from pathlib import Path

# Extension to emoji icon mapping
# Using emojis that visually represent each file type
ICON_MAPPING: Dict[str, str] = {
    # Python
    ".py": "🐍",
    # TypeScript
    ".ts": "🔷",
    ".tsx": "🔷",
    # JavaScript
    ".js": "🟨",
    ".jsx": "🟨",
    ".mjs": "🟨",
    ".cjs": "🟨",
    # Java / Kotlin
    ".java": "☕",
    ".kt": "🟪",
    ".kts": "🟪",
    ".gradle": "🐘",
    ".properties": "⚙️",
    ".pro": "⚙️",
    # iOS / Apple
    ".swift": "🍎",
    ".m": "🍎",
    ".mm": "🍎",
    ".h": "📋",
    ".hpp": "📋",
    ".pbxproj": "📋",
    ".plist": "📋",
    ".xcconfig": "⚙️",
    # Web UI
    ".html": "🌐",
    ".css": "🎨",
    ".scss": "🎨",
    ".sass": "🎨",
    ".less": "🎨",
    ".vue": "💚",
    ".svelte": "🔥",
    # Shell
    ".sh": "🖥️",
    ".bash": "🖥️",
    ".zsh": "🖥️",
    # Flutter / Dart
    ".dart": "🎯",
    # Config / Docs
    ".json": "📋",
    ".yaml": "📝",
    ".yml": "📝",
    ".xml": "📄",
    ".toml": "📝",
    ".graphql": "📊",
    ".gql": "📊",
    ".md": "📕",
    ".txt": "📄",
    # Special filenames
    "Dockerfile": "🐳",
    "Makefile": "🔧",
    "Gemfile": "💎",
    "Podfile": "📱",
    "Fastfile": "🚀",
    "Jenkinsfile": "🔧",
    "package.json": "📦",
    "requirements.txt": "📋",
    "pyproject.toml": "📋",
    "tsconfig.json": "📘",
    "build.gradle": "🐘",
    "build.gradle.kts": "🐘",
    "settings.gradle": "🐘",
    "settings.gradle.kts": "🐘",
    "gradle.properties": "⚙️",
    "AndroidManifest.xml": "🤖",
}

# Category-level icon fallbacks
CATEGORY_ICONS: Dict[str, str] = {
    "python": "🐍",
    "typescript": "🔷",
    "javascript": "🟨",
    "java_kotlin": "☕",
    "ios_apple": "🍎",
    "web_ui": "🌐",
    "shell": "🖥️",
    "flutter": "🎯",
    "config_docs": "📋",
}

# Icon to display name mapping for file summary
ICON_NAMES: Dict[str, str] = {
    "🐍": "Python",
    "🔷": "TypeScript",
    "🟨": "JavaScript",
    "☕": "Java",
    "🟪": "Kotlin",
    "🐘": "Gradle",
    "🍎": "Swift",
    "🌐": "HTML",
    "🎨": "CSS",
    "💚": "Vue",
    "🔥": "Svelte",
    "🖥️": "Shell",
    "🎯": "Dart",
    "📋": "JSON",
    "📝": "YAML",
    "📄": "XML",
    "📕": "Markdown",
    "🐳": "Docker",
    "🔧": "Makefile",
    "💎": "Ruby",
    "📱": "CocoaPods",
    "🚀": "Fastlane",
    "📦": "Node.js",
    "📘": "Config",
    "⚙️": "Properties",
    "🤖": "Android",
    "📊": "GraphQL",
}


def get_file_icon(filename: str, category: str | None = None) -> str:
    """Get the emoji icon for a file based on its extension or name."""
    # Check exact filename first
    if filename in ICON_MAPPING:
        return ICON_MAPPING[filename]

    # Check extension
    ext = Path(filename).suffix.lower()
    if ext in ICON_MAPPING:
        return ICON_MAPPING[ext]

    # Fallback based on category
    if category and category in CATEGORY_ICONS:
        return CATEGORY_ICONS[category]

    # Default icon
    return "📄"


def get_icon_display_name(icon: str) -> str:
    """Get the display name for an icon."""
    return ICON_NAMES.get(icon, "Other")


def get_icon_with_name(filename: str, category: str | None = None) -> Tuple[str, str]:
    """Get both icon and display name for a file."""
    icon = get_file_icon(filename, category)
    name = get_icon_display_name(icon)
    return icon, name
