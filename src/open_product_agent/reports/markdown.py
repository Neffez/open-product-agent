from __future__ import annotations

from datetime import UTC, datetime

from open_product_agent.models.item import Item
from open_product_agent.models.profile import ProductProfile
from open_product_agent.models.score import ItemScore


def render_report(
    *,
    profile: ProductProfile,
    scored_items: list[tuple[Item, ItemScore]],
    top: int,
) -> str:
    lines = [
        f"# Product Report: {profile.name}",
        "",
        f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Domain: {profile.domain}",
        "",
    ]

    if not scored_items:
        lines.extend(["No items found for this profile.", ""])
        return "\n".join(lines)

    for index, (item, score) in enumerate(scored_items[:top], start=1):
        lines.extend(
            [
                f"## {index}. {item.title or item.id}",
                "",
                f"Overall score: {score.overall_score}/100",
                "",
                f"- Price: {_format_price(item)}",
                f"- Year: {_format_attribute(item, 'year')}",
                f"- Mileage: {_format_mileage(item)}",
                f"- Fuel: {_format_attribute(item, 'fuel')}",
                f"- Transmission: {_format_attribute(item, 'transmission')}",
                f"- Location: {item.location or 'unknown'}",
                f"- Seller type: {item.seller_type or 'unknown'}",
                f"- Source: {_format_source(item)}",
                f"- Fit score: {score.fit_score}/100",
                f"- Value score: {score.value_score}/100",
                f"- Risk score: {score.risk_score}/100",
                f"- Condition score: {score.condition_score}/100",
                f"- Convenience score: {score.convenience_score}/100",
                "",
                "### Rule-Based Notes",
                "",
                score.explanation,
                "",
            ]
        )
    return "\n".join(lines)


def _format_price(item: Item) -> str:
    if item.price is None:
        return "unknown"
    return f"{item.price} {item.currency or ''}".strip()


def _format_attribute(item: Item, key: str) -> str:
    value = item.attributes.get(key)
    return str(value) if value not in (None, "") else "unknown"


def _format_mileage(item: Item) -> str:
    value = item.attributes.get("mileage_km")
    return f"{value} km" if value not in (None, "") else "unknown"


def _format_source(item: Item) -> str:
    if item.source_url:
        return str(item.source_url)
    return item.source_name or "unknown"
