from __future__ import annotations

from open_product_agent.models.analysis import ItemAnalysis

ITEM_ANALYSIS_SCHEMA_NAME = "item_analysis"
ITEM_ANALYSIS_SCHEMA = ItemAnalysis.model_json_schema()
