"""Insight categories module.

This module auto-imports all category implementations to trigger
registration with the category registry.

To add a new category:
1. Create a new file (e.g., sector_rotation.py)
2. Define a class inheriting from InsightCategoryBase
3. Use @register_category decorator
4. Import it in this file
"""

# Import all category implementations to trigger registration
from .ai_sector_risk import AISectorRiskCategory

__all__ = [
    "AISectorRiskCategory",
]
