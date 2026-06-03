"""Read-only policy document search."""
from __future__ import annotations

from pathlib import Path

from app.core.config import settings

_ALLOWED_EXTENSIONS = {".md", ".txt", ".json"}


def search_policy_documents(query: str, doc_type: str | None = None) -> dict:
    """Return short keyword excerpts from static policy documents.

    `doc_type` is reserved for future directory/tag filtering. MVP searches all allowed
    static documents under POLICY_DOCS_PATH.
    """
    del doc_type
    query = query.strip().lower()
    if not query:
        return {"excerpts": []}

    root = Path(settings.policy_docs_path)
    if not root.exists() or not root.is_dir():
        return {"excerpts": []}

    excerpts: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _ALLOWED_EXTENSIONS:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        lower = text.lower()
        index = lower.find(query)
        if index < 0:
            continue
        start = max(0, index - 160)
        end = min(len(text), index + len(query) + 240)
        heading = next((line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("#")), path.stem)
        excerpts.append(
            {
                "heading": heading,
                "text": text[start:end].strip(),
                "source": str(path.relative_to(root)),
            }
        )
        if len(excerpts) >= 5:
            break
    return {"excerpts": excerpts}
