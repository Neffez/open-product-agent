from __future__ import annotations

from datetime import UTC, datetime

from open_product_agent.models.domain_pack import DomainPack
from open_product_agent.models.item import Item
from open_product_agent.models.profile import ProductProfile
from open_product_agent.models.score import ItemScore


def calculate_scores(
    profile: ProductProfile,
    items: list[Item],
    *,
    profile_id: str,
    domain_pack: DomainPack | None = None,
) -> list[ItemScore]:
    return [
        _score_item(profile, item, profile_id=profile_id, domain_pack=domain_pack)
        for item in items
    ]


def _score_item(
    profile: ProductProfile,
    item: Item,
    *,
    profile_id: str,
    domain_pack: DomainPack | None,
) -> ItemScore:
    fit_score = 100
    value_score = 100
    risk_score = 100
    condition_score = 70
    convenience_score = 70
    reasons: list[str] = []

    max_price = _constraint_int(profile, "max_price") or (profile.budget.max if profile.budget else None)
    if max_price is not None and item.price is not None and item.price > max_price:
        value_score -= 40
        fit_score -= 25
        reasons.append(f"price exceeds max budget ({item.price} > {max_price})")

    min_year = _constraint_int(profile, "min_year")
    year = _attribute_int(item, "year")
    if min_year is not None and year is not None and year < min_year:
        fit_score -= 20
        reasons.append(f"year is below minimum ({year} < {min_year})")

    max_mileage = _constraint_int(profile, "max_mileage_km")
    mileage = _attribute_int(item, "mileage_km")
    if max_mileage is not None and mileage is not None and mileage > max_mileage:
        condition_score -= 25
        risk_score -= 10
        reasons.append(f"mileage exceeds maximum ({mileage} > {max_mileage})")

    missing_must_have = [
        feature for feature in profile.must_have if not _has_signal(item, feature, domain_pack)
    ]
    if missing_must_have:
        fit_score -= 15 * len(missing_must_have)
        reasons.append("missing must-have evidence: " + ", ".join(missing_must_have))

    nice_to_have_matches = [
        feature for feature in profile.nice_to_have if _has_signal(item, feature, domain_pack)
    ]
    if nice_to_have_matches:
        fit_score += min(10, 3 * len(nice_to_have_matches))
        reasons.append("nice-to-have evidence: " + ", ".join(nice_to_have_matches))

    if not item.title:
        risk_score -= 10
        reasons.append("title is missing")

    overall_score = round(
        (_clamp(fit_score) * 0.40)
        + (_clamp(value_score) * 0.20)
        + (_clamp(risk_score) * 0.20)
        + (_clamp(condition_score) * 0.10)
        + (_clamp(convenience_score) * 0.10)
    )
    explanation = "; ".join(reasons) if reasons else "No obvious rule-based issues detected."

    return ItemScore(
        id=f"score_{profile_id}_{item.id}",
        item_id=item.id,
        profile_id=profile_id,
        fit_score=_clamp(fit_score),
        value_score=_clamp(value_score),
        risk_score=_clamp(risk_score),
        condition_score=_clamp(condition_score),
        convenience_score=_clamp(convenience_score),
        overall_score=_clamp(overall_score),
        explanation=explanation,
        created_at=datetime.now(UTC),
    )


def profile_id_from_name(name: str) -> str:
    normalized = "".join(character.lower() if character.isalnum() else "_" for character in name)
    return "_".join(part for part in normalized.split("_") if part)


def _constraint_int(profile: ProductProfile, key: str) -> int | None:
    value = profile.hard_constraints.get(key)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _attribute_int(item: Item, key: str) -> int | None:
    value = item.attributes.get(key)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _has_signal(item: Item, feature: str, domain_pack: DomainPack | None) -> bool:
    signals = [feature, *_synonyms_for(feature, domain_pack)]
    if item.attributes.get(feature) is True:
        return True
    if str(item.attributes.get(feature)).lower() in {"true", "yes", "ja", "included"}:
        return True
    haystack = " ".join(
        str(value) for value in [item.title, *item.attributes.keys(), *item.attributes.values()]
    )
    normalized_haystack = _normalize_signal(haystack)
    normalized_tokens = set(_normalize_tokens(haystack))
    return any(_signal_matches(signal, normalized_haystack, normalized_tokens) for signal in signals)


def _synonyms_for(feature: str, domain_pack: DomainPack | None) -> list[str]:
    if domain_pack is None:
        return []
    synonyms = domain_pack.synonyms.get(feature)
    if isinstance(synonyms, list):
        return synonyms
    if isinstance(synonyms, dict):
        return [synonym for values in synonyms.values() for synonym in values]
    return []


def _normalize_signal(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _normalize_tokens(value: str) -> list[str]:
    current = []
    tokens = []
    for character in value:
        if character.isalnum():
            current.append(character.lower())
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def _signal_matches(signal: str, normalized_haystack: str, normalized_tokens: set[str]) -> bool:
    normalized_signal = _normalize_signal(signal)
    if not normalized_signal:
        return False
    if len(normalized_signal) <= 3:
        return normalized_signal in normalized_tokens
    return normalized_signal in normalized_haystack


def _clamp(value: int) -> int:
    return max(0, min(100, value))
