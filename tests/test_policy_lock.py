import json
from pathlib import Path

from build_ai_context import constants

POLICY = Path(__file__).resolve().parents[1] / "ide" / "policy" / "policy.json"


def test_policy_file_exists():
    assert POLICY.is_file()


def test_limits_match_constants():
    data = json.loads(POLICY.read_text(encoding="utf-8"))
    assert data["bundleMaxLines"] == constants.DEFAULT_MAX_LINES
    assert data["largeFileWarnLines"] == constants.LARGE_FILE_WARN_LINES
    assert data["largeFileSkipLines"] == constants.LARGE_FILE_SKIP_LINES
    assert data["textEncoding"] == constants.DEFAULT_TEXT_ENCODING
    assert data["defaultOutputDir"] == constants.DEFAULT_OUTPUT_DIR


def test_categories_match_constants():
    data = json.loads(POLICY.read_text(encoding="utf-8"))
    assert {k: sorted(v) for k, v in data["categoryExtensions"].items()} == {
        k: sorted(v) for k, v in constants.CATEGORY_EXTENSIONS.items()
    }
    assert data["categoryAliases"] == constants.CATEGORY_ALIASES
    assert data["categoryDescriptions"] == constants.CATEGORY_DESCRIPTIONS
    assert sorted(data["specialFilenames"]) == sorted(constants.SPECIAL_FILENAMES)
    assert sorted(data["defaultExcludedDirs"]) == sorted(constants.DEFAULT_EXCLUDED_DIRS)
    assert sorted(data["defaultExcludedPrefixes"]) == sorted(constants.DEFAULT_EXCLUDED_PREFIXES)
    assert sorted(data["extraExcludedPatterns"]) == sorted(constants.EXTRA_EXCLUDED_PATTERNS)
    assert sorted(data["defaultSecretPatterns"]) == sorted(constants.DEFAULT_SECRET_PATTERNS)
