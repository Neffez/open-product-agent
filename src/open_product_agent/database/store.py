from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from open_product_agent.database.schema import SCHEMA_SQL
from open_product_agent.models.item import ImportRun, Item, ItemSnapshot
from open_product_agent.models.profile import ProductProfile
from open_product_agent.models.score import ItemScore


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path

    def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA_SQL)

    def save_profile(self, profile_id: str, profile: ProductProfile) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT created_at FROM profiles WHERE id = ?",
                (profile_id,),
            ).fetchone()
            created_at = existing["created_at"] if existing else now
            connection.execute(
                """
                INSERT OR REPLACE INTO profiles (
                  id, name, domain, profile_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_id,
                    profile.name,
                    profile.domain,
                    profile.model_dump_json(),
                    created_at,
                    now,
                ),
            )

    def save_import_run(self, import_run: ImportRun) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO import_runs (
                  id, source_id, started_at, finished_at, status, items_seen,
                  items_created, items_updated, error_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    import_run.id,
                    import_run.source_id,
                    import_run.started_at.isoformat(),
                    import_run.finished_at.isoformat() if import_run.finished_at else None,
                    import_run.status,
                    import_run.items_seen,
                    import_run.items_created,
                    import_run.items_updated,
                    json.dumps(import_run.errors),
                ),
            )

    def upsert_item_with_snapshot(self, item: Item, snapshot: ItemSnapshot) -> bool:
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT id, first_seen_at FROM items WHERE id = ?",
                (item.id,),
            ).fetchone()
            created = existing is None
            first_seen_at = existing["first_seen_at"] if existing else item.first_seen_at.isoformat()
            connection.execute(
                """
                INSERT OR REPLACE INTO items (
                  id, domain, source_name, source_url, title, price, currency,
                  location, seller_type, attributes_json, first_seen_at,
                  last_seen_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.domain,
                    item.source_name,
                    str(item.source_url) if item.source_url else None,
                    item.title,
                    item.price,
                    item.currency,
                    item.location,
                    item.seller_type,
                    json.dumps(item.attributes, sort_keys=True),
                    first_seen_at,
                    item.last_seen_at.isoformat(),
                    item.status,
                ),
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO item_snapshots (
                  id, item_id, import_run_id, observed_at, title, price, currency,
                  description, raw_data_json, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.id,
                    snapshot.item_id,
                    snapshot.import_run_id,
                    snapshot.observed_at.isoformat(),
                    snapshot.title,
                    snapshot.price,
                    snapshot.currency,
                    snapshot.description,
                    json.dumps(snapshot.raw_data, sort_keys=True),
                    snapshot.content_hash,
                ),
            )
        return created

    def list_items(self, domain: str | None = None) -> list[Item]:
        query = "SELECT * FROM items"
        parameters: tuple[str, ...] = ()
        if domain:
            query += " WHERE domain = ?"
            parameters = (domain,)
        query += " ORDER BY last_seen_at DESC, id ASC"

        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._row_to_item(row) for row in rows]

    def save_scores(self, scores: list[ItemScore]) -> None:
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT OR REPLACE INTO item_scores (
                  id, item_id, profile_id, analysis_run_id, fit_score, value_score,
                  risk_score, condition_score, convenience_score, overall_score,
                  explanation, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        score.id,
                        score.item_id,
                        score.profile_id,
                        score.analysis_run_id,
                        score.fit_score,
                        score.value_score,
                        score.risk_score,
                        score.condition_score,
                        score.convenience_score,
                        score.overall_score,
                        score.explanation,
                        score.created_at.isoformat(),
                    )
                    for score in scores
                ],
            )

    def list_scores(self, profile_id: str) -> list[ItemScore]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM item_scores
                WHERE profile_id = ?
                ORDER BY overall_score DESC, item_id ASC
                """,
                (profile_id,),
            ).fetchall()
        return [self._row_to_score(row) for row in rows]

    def get_item(self, item_id: str) -> Item | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        return self._row_to_item(row) if row else None

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> Item:
        return Item(
            id=row["id"],
            domain=row["domain"],
            source_name=row["source_name"],
            source_url=row["source_url"],
            title=row["title"],
            price=row["price"],
            currency=row["currency"],
            location=row["location"],
            seller_type=row["seller_type"],
            attributes=json.loads(row["attributes_json"] or "{}"),
            first_seen_at=datetime.fromisoformat(row["first_seen_at"]),
            last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
            status=row["status"],
        )

    @staticmethod
    def _row_to_score(row: sqlite3.Row) -> ItemScore:
        return ItemScore(
            id=row["id"],
            item_id=row["item_id"],
            profile_id=row["profile_id"],
            analysis_run_id=row["analysis_run_id"],
            fit_score=row["fit_score"],
            value_score=row["value_score"],
            risk_score=row["risk_score"],
            condition_score=row["condition_score"],
            convenience_score=row["convenience_score"],
            overall_score=row["overall_score"],
            explanation=row["explanation"] or "",
            created_at=datetime.fromisoformat(row["created_at"]),
        )
