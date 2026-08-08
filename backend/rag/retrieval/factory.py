from functools import lru_cache

from django.conf import settings

from rag.retrieval.base import Retriever


@lru_cache
def get_retriever() -> Retriever:
    strategy = settings.RETRIEVAL_STRATEGY
    # "lexical"/"dense" stay unwrapped deliberately: they exist to
    # evaluate one half's isolated quality (see test_retrieval_quality.py),
    # and forcing in date matches would corrupt that measurement.
    if strategy == "lexical":
        from rag.retrieval.lexical import LexicalRetriever

        return LexicalRetriever()
    if strategy == "dense":
        from rag.retrieval.dense import DenseRetriever

        return DenseRetriever()
    if strategy == "hybrid":
        from rag.retrieval.date_matching import DateAwareRetriever
        from rag.retrieval.hybrid import HybridRetriever

        return DateAwareRetriever(HybridRetriever())
    if strategy == "hybrid_reranked":
        from rag.retrieval.date_matching import DateAwareRetriever
        from rag.retrieval.hybrid import HybridRetriever
        from rag.retrieval.reranking import RerankingRetriever

        return DateAwareRetriever(RerankingRetriever(HybridRetriever()))
    raise ValueError(f"Unknown RETRIEVAL_STRATEGY: {strategy!r}")
