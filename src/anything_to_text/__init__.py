"""
anything_to_text - Export source code into AI-friendly text bundles.

This package provides tools to export source code and project files into
AI-friendly bundle text files with a compact manifest for easy AI analysis.
"""

__version__ = "0.3.3"

from anything_to_text.exporter import CodeExporter, ExportConfig, ExportResult

__all__ = [
    "CodeExporter",
    "ExportConfig",
    "ExportResult",
    "__version__",
]
