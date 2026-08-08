from django.conf import settings

from rag.embeddings.base import EmbeddingProvider


class LocalEmbeddingProvider(EmbeddingProvider):
    """A bi-encoder running entirely in-process via sentence-transformers
    — no external API, so no rate limit. Same motivation as
    rag.reranking.local.LocalReranker: Voyage's free-tier rate limit
    repeatedly broke real usage (see docs/roadmap.md, Etapa 9/10 notes).

    Default model (settings.LOCAL_EMBEDDING_MODEL) is
    intfloat/multilingual-e5-large: 100 languages, MIT licensed, and —
    the deciding factor — it outputs 1024-dimensional vectors natively,
    matching settings.EMBEDDING_DIMENSIONS exactly. pgvector's column
    dimension is fixed at migration time; picking a model with a
    different output size would mean a real schema migration and a full
    re-embed, not just a settings change. The smaller e5-base/e5-small
    variants in the same family output fewer dimensions, not the same
    count at lower quality — "large" is the only one that fits the
    existing column without one.

    E5 models are trained on explicit "query: "/"passage: " prefixes for
    asymmetric retrieval — omitting them measurably hurts quality per the
    model's own documentation. That maps directly onto this interface's
    embed_query/embed_documents split: the same asymmetry Voyage's
    input_type="query"|"document" achieves through an internal prompt
    instead of an explicit prefix.
    """

    def __init__(self) -> None:
        self._model = None

    def _sentence_transformer(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(settings.LOCAL_EMBEDDING_MODEL)
        return self._model

    @property
    def dimensions(self) -> int:
        return settings.EMBEDDING_DIMENSIONS

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        prefixed = [f"passage: {text}" for text in texts]
        vectors = self._sentence_transformer().encode(prefixed, normalize_embeddings=True)
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        vector = self._sentence_transformer().encode(f"query: {text}", normalize_embeddings=True)
        return vector.tolist()
