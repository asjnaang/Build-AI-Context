#!/bin/bash
set -e

echo "=== Building anything-to-text ==="

# Activate virtual environment if it exists
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
    source "$SCRIPT_DIR/.venv/bin/activate"
fi

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf dist/ build/ src/*.egg-info *.egg-info

# Build
echo "Building package..."
python -m build

echo ""
echo "=== Build complete ==="
echo "Created files:"
ls -la dist/

echo ""
echo "=== To publish ==="
echo ""
echo "Test locally first:"
echo "  pip install dist/anything_to_text-*.whl"
echo "  anything-to-text --version"
echo ""
echo "Upload to TestPyPI (recommended first):"
echo "  twine upload --repository testpypi dist/*"
echo ""
echo "Upload to PyPI:"
echo "  twine upload dist/*"
