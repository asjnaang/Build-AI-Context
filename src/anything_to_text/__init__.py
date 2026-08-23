"""
anything_to_text - Export source code into AI-friendly text bundles.

This package provides tools to export source code and project files into
AI-friendly bundle text files with a compact manifest for easy AI analysis.
"""

from importlib.metadata import version

__version__ = version("anything-to-text")

from anything_to_text.exporter import CodeExporter, ExportConfig, ExportResult

__all__ = [
    "CodeExporter",
    "ExportConfig",
    "ExportResult",
    "__version__",
]
