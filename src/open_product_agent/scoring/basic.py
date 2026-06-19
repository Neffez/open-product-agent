from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from open_product_agent.models.domain_pack import DomainPack
from open_product_agent.models.feedback import FeedbackEvent
from open_product_agent.models.item import Item
from open_product_agent.models.profile import ProductProfile
from open_product_agent.models.score import ItemScore


def calculate_scores(
    profile: ProductProfile,
    items: list[Item],
    *,
    profile_id: str,
    domain_pack: DomainPack | None = None,
    analyses_by_item: dict[str, dict[str, Any]] | None = None,
    feedback_by_item: dict[str, list[FeedbackEvent]] | None = None,
) -> list[ItemScore]:
    return [
        _score_item(
            profile,
            item,
            profile_id=profile_id,
            domain_pack=domain_pack,
            analysis=(analyses_by_item or {}).get(item.id),
            feedback_events=(feedback_by_item or {}).get(item.id, []),
        )
        for item in items
    ]


def _score_item(
    profile: ProductProfile,
    item: Item,
    *,
    profile_id: str,
    domain_pack: DomainPack | None,
    analysis: dict[str, Any] | None,
    feedback_events: list[FeedbackEvent],
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
        feature
        for feature in profile.must_have
        if not _has_signal(item, feature, domain_pack, analysis)
    ]
    if missing_must_have:
        fit_score -= 15 * len(missing_must_have)
        reasons.append("missing must-have evidence: " + ", ".join(missing_must_have))

    nice_to_have_matches = [
        feature for feature in profile.nice_to_have if _has_signal(item, feature, domain_pack, analysis)
    ]
    if nice_to_have_matches:
        fit_score += min(10, 3 * len(nice_to_have_matches))
        reasons.append("nice-to-have evidence: " + ", ".join(nice_to_have_matches))

    if not item.title:
        risk_score -= 10
        reasons.append("title is missing")

    rule_flags = _evaluate_domain_risk_rules(item, domain_pack, analysis)
    if rule_flags:
        risk_score -= min(35, sum(penalty for _, penalty in rule_flags))
        reasons.append("domain risk rules: " + ", ".join(flag for flag, _ in rule_flags))

    if analysis:
        risk_flags = analysis.get("risk_flags") or []
        if risk_flags:
            risk_score -= min(30, 5 * len(risk_flags))
            reasons.append("AI risk flags: " + ", ".join(str(flag) for flag in risk_flags))

        missing_information = analysis.get("missing_information") or []
        if missing_information:
            risk_score -= min(15, 3 * len(missing_information))
            reasons.append(
                "AI missing information: "
                + ", ".join(str(field) for field in missing_information[:5])
            )

    feedback_reasons = _apply_feedback_adjustments(
        feedback_events,
        score_parts={
            "fit": fit_score,
            "value": value_score,
            "risk": risk_score,
            "condition": condition_score,
            "convenience": convenience_score,
        },
    )
    fit_score = feedback_reasons["scores"]["fit"]
    value_score = feedback_reasons["scores"]["value"]
    risk_score = feedback_reasons["scores"]["risk"]
    condition_score = feedback_reasons["scores"]["condition"]
    convenience_score = feedback_reasons["scores"]["convenience"]
    reasons.extend(feedback_reasons["reasons"])

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


def _evaluate_domain_risk_rules(
    item: Item,
    domain_pack: DomainPack | None,
    analysis: dict[str, Any] | None,
) -> list[tuple[str, int]]:
    if domain_pack is None:
        return []
    triggered = []
    for rule in domain_pack.risk_rules:
        value = _attribute_value(item, rule.attribute, analysis)
        if _risk_rule_matches(rule.operator, value, rule.value, item, rule.source_synonyms):
            triggered.append((rule.flag, rule.penalty))
    return triggered


def _apply_feedback_adjustments(
    feedback_events: list[FeedbackEvent],
    *,
    score_parts: dict[str, int],
) -> dict[str, Any]:
    scores = score_parts.copy()
    reasons = []
    for event in feedback_events:
        if event.feedback_type == "too_expensive":
            scores["value"] -= 20
        elif event.feedback_type == "too_far_away":
            scores["convenience"] -= 20
        elif event.feedback_type == "too_risky":
            scores["risk"] -= 20
        elif event.feedback_type in {"wrong_brand", "missing_feature", "not_my_style"}:
            scores["fit"] -= 15
        elif event.feedback_type == "favorite":
            scores["fit"] += 10
            scores["value"] += 5
        elif event.feedback_type == "ignore":
            scores["fit"] -= 60
            scores["risk"] -= 20
        reasons.append(
            "feedback adjustment: "
            + event.feedback_type
            + (f" ({event.reason})" if event.reason else "")
        )
    return {
        "scores": {key: _clamp(value) for key, value in scores.items()},
        "reasons": reasons,
    }


def _attribute_value(item: Item, key: str | None, analysis: dict[str, Any] | None) -> Any:
    if key is None:
        return None
    detected_attributes = analysis.get("detected_attributes") if analysis else None
    if isinstance(detected_attributes, dict) and key in detected_attributes:
        return detected_attributes[key]
    if key in item.attributes:
        return item.attributes[key]
    return getattr(item, key, None)


def _risk_rule_matches(
    operator: str,
    value: Any,
    expected: Any,
    item: Item,
    source_synonyms: list[str],
) -> bool:
    if operator == "greater_than":
        try:
            return value is not None and float(value) > float(expected)
        except (TypeError, ValueError):
            return False
    if operator == "missing_or_unknown":
        if value not in (None, "", "unknown"):
            return False
        if not source_synonyms:
            return True
        haystack = _item_haystack(item)
        normalized_haystack = _normalize_signal(haystack)
        normalized_tokens = set(_normalize_tokens(haystack))
        return not any(
            _signal_matches(synonym, normalized_haystack, normalized_tokens)
            for synonym in source_synonyms
        )
    if operator == "text_shorter_than":
        if not isinstance(value, str):
            return True
        try:
            return len(value.strip()) < int(expected)
        except (TypeError, ValueError):
            return False
    return False


def _has_signal(
    item: Item,
    feature: str,
    domain_pack: DomainPack | None,
    analysis: dict[str, Any] | None,
) -> bool:
    signals = [feature, *_synonyms_for(feature, domain_pack)]
    detected_attributes = analysis.get("detected_attributes") if analysis else None
    if isinstance(detected_attributes, dict):
        value = detected_attributes.get(feature)
        if value is True or str(value).lower() in {"true", "yes", "ja", "included"}:
            return True
    if item.attributes.get(feature) is True:
        return True
    if str(item.attributes.get(feature)).lower() in {"true", "yes", "ja", "included"}:
        return True
    haystack = _item_haystack(item)
    normalized_haystack = _normalize_signal(haystack)
    normalized_tokens = set(_normalize_tokens(haystack))
    return any(_signal_matches(signal, normalized_haystack, normalized_tokens) for signal in signals)


def _item_haystack(item: Item) -> str:
    return " ".join(
        str(value) for value in [item.title, *item.attributes.keys(), *item.attributes.values()]
    )


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
