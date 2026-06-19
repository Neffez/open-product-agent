from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st

from open_product_agent.database.store import Store
from open_product_agent.scoring.basic import profile_id_from_name
from open_product_agent.workflows import (
    add_feedback_event,
    analyze_profile,
    import_paths,
    load_profile,
    render_profile_report,
    score_profile,
)

DEFAULT_DB = os.getenv("OPA_DATABASE_PATH", "data/open_product_agent.sqlite3")
DEFAULT_PROFILE = os.getenv("OPA_PROFILE_PATH", "examples/profiles/family_car.yml")


def main() -> None:
    st.set_page_config(page_title="Open Product Agent", layout="wide")
    st.title("Open Product Agent")

    db_path, profile_path = _sidebar_paths()
    profile = _load_profile_or_stop(profile_path)
    store = Store(db_path)
    store.init()
    store.save_profile(profile_id_from_name(profile.name), profile)

    left, right = st.columns([0.9, 1.1], gap="large")
    with left:
        _render_import_panel(profile_path, db_path)
        _render_actions_panel(profile_path, db_path)
    with right:
        _render_items_panel(profile_path, db_path)


def _sidebar_paths() -> tuple[Path, Path]:
    with st.sidebar:
        st.header("Workspace")
        db_path = Path(st.text_input("SQLite database", value=DEFAULT_DB))
        profile_path = Path(st.text_input("Profile YAML", value=DEFAULT_PROFILE))
        st.caption("Ollama runs outside this container. Set OLLAMA_BASE_URL to reach it.")
    return db_path, profile_path


def _load_profile_or_stop(profile_path: Path):
    try:
        return load_profile(profile_path)
    except Exception as exc:
        st.error(f"Could not load profile: {exc}")
        st.stop()


def _render_import_panel(profile_path: Path, db_path: Path) -> None:
    st.subheader("Import Sources")
    import_type = st.segmented_control(
        "Type",
        options=["html", "csv", "json"],
        default="html",
        label_visibility="collapsed",
    )
    uploaded_files = st.file_uploader(
        "Files",
        type=[import_type],
        accept_multiple_files=True,
    )
    if uploaded_files:
        st.write(
            [
                {"file": file.name, "size_kb": round(len(file.getvalue()) / 1024, 1)}
                for file in uploaded_files
            ]
        )
    if st.button("Import all", disabled=not uploaded_files):
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = []
            for file in uploaded_files or []:
                path = Path(temp_dir) / file.name
                path.write_bytes(file.getvalue())
                paths.append(path)
            try:
                import_run = import_paths(
                    paths,
                    profile_path=profile_path,
                    db_path=db_path,
                    import_type=str(import_type),
                )
            except Exception as exc:
                st.error(f"Import failed: {exc}")
                return
        st.success(
            f"Imported {import_run.items_seen} item(s): "
            f"{import_run.items_created} created, {import_run.items_updated} updated"
        )
        for error in import_run.errors:
            st.warning(error)


def _render_actions_panel(profile_path: Path, db_path: Path) -> None:
    st.subheader("Run")
    provider = st.selectbox("Provider", ["ollama", "openai"], index=0)
    default_model = "gemma4:latest" if provider == "ollama" else "gpt-4o-mini"
    model = st.text_input("Model", value=default_model)
    limit = st.number_input("Analyze limit", min_value=1, value=1, step=1)

    action_columns = st.columns(3)
    if action_columns[0].button("Analyze"):
        with st.spinner("Analyzing items"):
            try:
                analyzed, failed = analyze_profile(
                    profile_path=profile_path,
                    db_path=db_path,
                    provider_name=provider,
                    model=model,
                    limit=int(limit),
                )
            except Exception as exc:
                st.error(f"Analysis failed: {exc}")
            else:
                st.success(f"Analyzed {analyzed} item(s), {failed} failed")
    if action_columns[1].button("Score"):
        try:
            count = score_profile(profile_path=profile_path, db_path=db_path)
        except Exception as exc:
            st.error(f"Scoring failed: {exc}")
        else:
            st.success(f"Scored {count} item(s)")
    if action_columns[2].button("Build report"):
        try:
            report = render_profile_report(profile_path=profile_path, db_path=db_path, top=20)
        except Exception as exc:
            st.error(f"Report failed: {exc}")
        else:
            st.download_button(
                "Download report",
                data=report,
                file_name="open-product-agent-report.md",
                mime="text/markdown",
            )


def _render_items_panel(profile_path: Path, db_path: Path) -> None:
    st.subheader("Candidates")
    profile = load_profile(profile_path)
    profile_id = profile_id_from_name(profile.name)
    store = Store(db_path)
    scores = store.list_scores(profile_id)
    score_by_item = {score.item_id: score for score in scores}
    items = store.list_items(domain=profile.domain)

    if not items:
        st.info("No imported items yet.")
        return

    rows = []
    for item in items:
        score = score_by_item.get(item.id)
        rows.append(
            {
                "id": item.id,
                "title": item.title,
                "price": item.price,
                "location": item.location,
                "overall": score.overall_score if score else None,
                "risk": score.risk_score if score else None,
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)

    selected_id = st.selectbox("Selected item", [row["id"] for row in rows])
    selected_item = store.get_item(selected_id)
    if selected_item is None:
        return
    selected_score = score_by_item.get(selected_id)
    _render_item_detail(profile_path, db_path, selected_item, selected_score)


def _render_item_detail(profile_path: Path, db_path: Path, item, score) -> None:
    st.divider()
    st.subheader(item.title or item.id)
    metric_columns = st.columns(4)
    metric_columns[0].metric("Overall", score.overall_score if score else "not scored")
    metric_columns[1].metric("Fit", score.fit_score if score else "-")
    metric_columns[2].metric("Risk", score.risk_score if score else "-")
    metric_columns[3].metric("Value", score.value_score if score else "-")

    st.write(
        {
            "price": item.price,
            "currency": item.currency,
            "location": item.location,
            "source": item.source_url or item.source_name,
            "attributes": item.attributes,
        }
    )
    if score:
        st.markdown("#### Score Notes")
        st.write(score.explanation)

    profile = load_profile(profile_path)
    profile_id = profile_id_from_name(profile.name)
    analyses = Store(db_path).list_latest_valid_analyses(profile_id)
    analysis = analyses.get(item.id)
    if analysis and analysis.output:
        st.markdown("#### AI Recommendation")
        st.write(
            {
                "decision": analysis.output.get("recommendation"),
                "reason": analysis.output.get("recommendation_reason"),
                "next_steps": analysis.output.get("next_steps"),
                "seller_questions": analysis.output.get("seller_questions"),
            }
        )

    st.markdown("#### Feedback")
    reason = st.text_input("Reason", key=f"reason_{item.id}")
    feedback_columns = st.columns(4)
    for column, feedback_type in zip(
        feedback_columns,
        ["favorite", "ignore", "too_risky", "too_expensive"],
        strict=True,
    ):
        if column.button(feedback_type, key=f"{feedback_type}_{item.id}"):
            add_feedback_event(
                profile_path=profile_path,
                db_path=db_path,
                item_id=item.id,
                feedback_type=feedback_type,  # type: ignore[arg-type]
                reason=reason or None,
            )
            st.success(f"Recorded feedback: {feedback_type}")


if __name__ == "__main__":
    main()
