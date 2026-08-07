from functools import lru_cache

from django.conf import settings

from rag.retrieval.base import Retriever


@lru_cache
def get_retriever() -> Retriever:
    strategy = settings.RETRIEVAL_STRATEGY
    if strategy == "lexical":
        from rag.retrieval.lexical import LexicalRetriever

        return LexicalRetriever()
    if strategy == "dense":
        from rag.retrieval.dense import DenseRetriever

        return DenseRetriever()
    if strategy == "hybrid":
        from rag.retrieval.hybrid import HybridRetriever

        return HybridRetriever()
    if strategy == "hybrid_reranked":
        from rag.retrieval.hybrid import HybridRetriever
        from rag.retrieval.reranking import RerankingRetriever

        return RerankingRetriever(HybridRetriever())
    raise ValueError(f"Unknown RETRIEVAL_STRATEGY: {strategy!r}")
