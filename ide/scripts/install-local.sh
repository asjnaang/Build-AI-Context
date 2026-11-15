#!/usr/bin/env bash
set -euo pipefail

if [[ ${1:-} == --help ]]; then
  echo "Usage: ide/scripts/install-local.sh VSCODE_PROFILE ANDROID_STUDIO_CONFIG_DIR"
  exit 0
fi
if [[ $# -ne 2 ]]; then
  echo "Usage: ide/scripts/install-local.sh VSCODE_PROFILE ANDROID_STUDIO_CONFIG_DIR" >&2
  echo "Installs the already-built VSIX and Android Studio zip for local testing." >&2
  exit 2
fi

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
vsix="$repo_dir/ide/vscode/build-ai-context-0.1.0.vsix"
zip="$repo_dir/ide/intellij/plugin/build/distributions/plugin-0.1.0.zip"
code_bin=${CODE_BIN:-/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code}
profile=$1
android_config=$2
plugin_dir="$android_config/plugins/plugin"

[[ -f $vsix && -f $zip && -x $code_bin && -d $android_config ]] || {
  echo "Missing built package, VS Code CLI, or Android Studio config directory." >&2
  exit 1
}

"$code_bin" --install-extension "$vsix" --profile "$profile" --force
"$code_bin" --list-extensions --profile "$profile" | grep -Fxqi 'asjnaang.build-ai-context'

if [[ -d $plugin_dir ]]; then
  backup_dir="$HOME/Library/Caches/build-ai-context/plugin-backups/$(date -u +%Y%m%dT%H%M%SZ)"
  mkdir -p "$backup_dir"
  cp -R "$plugin_dir" "$backup_dir/plugin"
  echo "Previous Android Studio plugin: $backup_dir/plugin"
fi
mkdir -p "$android_config/plugins"
unzip -oq "$zip" -d "$android_config/plugins"
[[ -f $plugin_dir/lib/plugin-0.1.0.jar ]] || {
  echo "Android Studio plugin jar was not installed." >&2
  exit 1
}
echo "Installed VS Code profile $profile and Android Studio plugin in $plugin_dir"
echo "Reload VS Code and restart Android Studio to load these packages."
