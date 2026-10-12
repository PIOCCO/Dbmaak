from __future__ import annotations

import re

from knowledge.store import BusinessKnowledgeStore, KnowledgeDocument, KnowledgeSection


class KnowledgeRetriever:
    """Keyword-based retrieval over structured business knowledge (RAG-ready interface)."""

    def __init__(self, store: BusinessKnowledgeStore) -> None:
        self._store = store

    def search(self, query: str, *, limit: int = 3) -> list[KnowledgeDocument]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return self._store.all_documents()[:limit]

        scored: list[tuple[int, KnowledgeDocument]] = []
        for doc in self._store.all_documents():
            text = f"{doc.title} {doc.body}".lower()
            score = sum(1 for token in query_tokens if token in text)
            if score:
                scored.append((score, doc))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [doc for _, doc in scored[:limit]]

    def get_section(self, section: KnowledgeSection) -> KnowledgeDocument | None:
        for doc in self._store.all_documents():
            if doc.section == section:
                return doc
        return None

    def grounded_answer_prefix(self) -> str:
        return (
            "The following information is verified business data. "
            "Do not invent details not present here."
        )


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) >= 3]
