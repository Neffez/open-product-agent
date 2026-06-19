from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
    @abstractmethod
    def generate_profile(
        self,
        user_description: str,
        domain_pack: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate a structured product profile from a natural-language need."""

    @abstractmethod
    def analyze_item(
        self,
        profile: dict[str, Any],
        item_snapshot: dict[str, Any],
        domain_pack: dict[str, Any],
    ) -> dict[str, Any]:
        """Analyze one item snapshot and return validated structured data."""

    @abstractmethod
    def compare_items(
        self,
        profile: dict[str, Any],
        analyzed_items: list[dict[str, Any]],
        domain_pack: dict[str, Any],
    ) -> dict[str, Any]:
        """Compare analyzed items for report generation."""
