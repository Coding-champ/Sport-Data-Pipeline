"""
Sports Data Pipeline
Modulare Sportdaten-Plattform für Collection, Analytics und API
"""

__version__ = "1.0.0"
__author__ = "Sports Data Team"

# NOTE:
# Avoid importing heavy modules (like configuration) at package import time to
# keep "import src" lightweight and side-effect free, particularly for unit tests
# that only need subpackages such as scrapers.utils.

__all__ = []
