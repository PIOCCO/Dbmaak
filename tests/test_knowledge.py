from pathlib import Path

from business.registry import BusinessRegistry
from knowledge.store import BusinessKnowledgeStore, KnowledgeSection
from knowledge.retrieval import KnowledgeRetriever


def test_knowledge_marks_verified_sections() -> None:
    profile = BusinessRegistry.from_directory(Path("config/businesses")).get("demo_salon")
    store = BusinessKnowledgeStore(profile)
    sections = {doc.section for doc in store.all_documents()}
    assert KnowledgeSection.SERVICES in sections
    assert KnowledgeSection.HOURS in sections


def test_retriever_finds_hours() -> None:
    profile = BusinessRegistry.from_directory(Path("config/businesses")).get("demo_salon")
    retriever = KnowledgeRetriever(BusinessKnowledgeStore(profile))
    docs = retriever.search("opening hours Tuesday")
    assert docs
    assert any(d.section == KnowledgeSection.HOURS for d in docs)
