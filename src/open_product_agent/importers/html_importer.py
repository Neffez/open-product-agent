from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

from open_product_agent.models.item import Item, ItemSnapshot

from .normalizer import normalize_record


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        stripped = " ".join(data.split())
        if stripped:
            self.parts.append(stripped)

    def text(self) -> str:
        return "\n".join(self.parts)


def load_html(path: Path, *, domain: str, import_run_id: str) -> list[tuple[Item, ItemSnapshot]]:
    html = path.read_text(encoding="utf-8")
    parser = TextExtractor()
    parser.feed(html)
    text = parser.text()
    title = _extract_title(html) or path.stem
    record = {
        "id": path.stem,
        "source_name": "local_html",
        "source_url": path.resolve().as_uri(),
        "title": title,
        "description": text,
    }
    return [normalize_record(record, domain=domain, import_run_id=import_run_id)]


def _extract_title(html: str) -> str | None:
    parser = _TitleExtractor()
    parser.feed(html)
    return parser.title


class _TitleExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title and self.title is None:
            self.title = " ".join(data.split())
