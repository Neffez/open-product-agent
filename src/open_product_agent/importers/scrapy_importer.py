from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from open_product_agent.models.item import Item, ItemSnapshot

from .normalizer import normalize_record


class ScrapyRecipeSettings(BaseModel):
    obey_robots_txt: bool = True
    download_delay: float = Field(default=5.0, ge=1.0)
    max_pages: int = Field(default=25, ge=1, le=500)
    concurrent_requests: int = Field(default=1, ge=1, le=4)
    user_agent: str | None = None


class ScrapyRecipe(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    start_urls: list[str] = Field(min_length=1)
    allowed_domains: list[str] = Field(min_length=1)
    item_selector: str | None = None
    fields: dict[str, str] = Field(default_factory=dict)
    attributes: dict[str, str] = Field(default_factory=dict)
    follow_links: list[str] = Field(default_factory=list)
    settings: ScrapyRecipeSettings = Field(default_factory=ScrapyRecipeSettings)

    @field_validator("allowed_domains")
    @classmethod
    def normalize_allowed_domains(cls, value: list[str]) -> list[str]:
        domains = [domain.strip().lower() for domain in value if domain.strip()]
        if not domains:
            raise ValueError("allowed_domains must contain at least one domain")
        return domains

    @field_validator("start_urls")
    @classmethod
    def validate_start_urls(cls, value: list[str]) -> list[str]:
        for url in value:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"start_urls must contain absolute HTTP(S) URLs: {url}")
        return value

    @field_validator("fields")
    @classmethod
    def require_title_or_description(cls, value: dict[str, str]) -> dict[str, str]:
        if "title" not in value and "description" not in value:
            raise ValueError("fields must include at least title or description")
        return value

    @model_validator(mode="after")
    def require_start_urls_within_allowed_domains(self) -> ScrapyRecipe:
        for url in self.start_urls:
            host = urlparse(url).hostname or ""
            if not any(host == domain or host.endswith(f".{domain}") for domain in self.allowed_domains):
                raise ValueError(f"start URL is outside allowed_domains: {url}")
        return self


def load_scrapy_recipe_config(path: Path) -> ScrapyRecipe:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return ScrapyRecipe.model_validate(data)


def load_scrapy_recipe(
    path: Path,
    *,
    domain: str,
    import_run_id: str,
) -> list[tuple[Item, ItemSnapshot]]:
    recipe = load_scrapy_recipe_config(path)
    records = _crawl_recipe(recipe)
    return [
        normalize_record(record, domain=domain, import_run_id=import_run_id)
        for record in records
    ]


def _crawl_recipe(recipe: ScrapyRecipe) -> list[dict[str, Any]]:
    try:
        import scrapy
        from scrapy.crawler import CrawlerProcess
    except ImportError as exc:
        raise RuntimeError(
            "Scrapy support is not installed. Install with: python -m pip install -e .[crawler]"
        ) from exc

    records: list[dict[str, Any]] = []

    class RecipeSpider(scrapy.Spider):  # type: ignore[misc]
        name = recipe.name
        start_urls = recipe.start_urls
        allowed_domains = recipe.allowed_domains
        custom_settings = _scrapy_settings(recipe)

        def parse(self, response):  # type: ignore[no-untyped-def]
            selectors = response.css(recipe.item_selector) if recipe.item_selector else [response]
            for selector in selectors:
                record = _extract_record(selector, response.url, recipe)
                if record:
                    records.append(record)

            for link_selector in recipe.follow_links:
                for href in response.css(link_selector).getall():
                    yield response.follow(href, callback=self.parse)

    process = CrawlerProcess(settings={"LOG_ENABLED": False})
    process.crawl(RecipeSpider)
    process.start(stop_after_crawl=True, install_signal_handlers=False)
    return records


def _scrapy_settings(recipe: ScrapyRecipe) -> dict[str, Any]:
    settings: dict[str, Any] = {
        "ROBOTSTXT_OBEY": recipe.settings.obey_robots_txt,
        "DOWNLOAD_DELAY": recipe.settings.download_delay,
        "CONCURRENT_REQUESTS": recipe.settings.concurrent_requests,
        "CLOSESPIDER_PAGECOUNT": recipe.settings.max_pages,
        "COOKIES_ENABLED": False,
        "RETRY_ENABLED": False,
    }
    if recipe.settings.user_agent:
        settings["USER_AGENT"] = recipe.settings.user_agent
    return settings


def _extract_record(selector: Any, response_url: str, recipe: ScrapyRecipe) -> dict[str, Any]:
    record: dict[str, Any] = {"source_name": recipe.name}
    for field_name, css_query in recipe.fields.items():
        value = _extract_first(selector, css_query)
        if field_name == "source_url" and value:
            value = selector.root.base_url if value == "." else value
            value = _urljoin_from_selector(selector, response_url, value)
        if value:
            record[field_name] = value

    attributes: dict[str, Any] = {}
    for field_name, css_query in recipe.attributes.items():
        value = _extract_first(selector, css_query)
        if value:
            attributes[field_name] = value
    if attributes:
        record["attributes"] = attributes
    if "source_url" not in record:
        record["source_url"] = response_url
    return record


def _extract_first(selector: Any, css_query: str) -> str | None:
    values = [" ".join(value.split()) for value in selector.css(css_query).getall()]
    values = [value for value in values if value]
    if not values:
        return None
    return " ".join(values)


def _urljoin_from_selector(selector: Any, response_url: str, value: str) -> str:
    return urljoin(response_url, value)
