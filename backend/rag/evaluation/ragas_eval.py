import os
from collections.abc import Sequence
from functools import lru_cache

# Must run before `import ragas`: ragas/experiment.py imports GitPython at
# module load time for an experiment-tracking feature this codebase never
# uses, and GitPython raises ImportError on init if it can't find a `git`
# binary -- which our runtime image deliberately doesn't have (it's not
# needed to run Django). "quiet" tells GitPython to degrade instead of
# raising, which is exactly what we want for a feature we never call.
os.environ.setdefault("GIT_PYTHON_REFRESH", "quiet")

from django.conf import settings  # noqa: E402
from langchain_anthropic import ChatAnthropic  # noqa: E402
from langchain_core.embeddings import Embeddings  # noqa: E402
from ragas import EvaluationDataset, MultiTurnSample, SingleTurnSample, evaluate  # noqa: E402
from ragas.embeddings.base import BaseRagasEmbeddings, LangchainEmbeddingsWrapper  # noqa: E402
from ragas.llms.base import BaseRagasLLM, LangchainLLMWrapper  # noqa: E402
from ragas.metrics import (  # noqa: E402
    Faithfulness,
    LLMContextPrecisionWithReference,
    LLMContextRecall,
    ResponseRelevancy,
)
from ragas.metrics.base import Metric  # noqa: E402

from rag.embeddings.factory import get_embedding_provider

# Imported from ragas.llms.base / ragas.embeddings.base, not the top-level
# ragas.llms / ragas.embeddings -- those re-export both wrapper classes
# through a DeprecationHelper proxy (pointing at ragas.llms.llm_factory
# instead), which isn't usable for isinstance checks and prints a warning
# on every construction. The deprecation notice doesn't actually apply
# here: llm_factory's return type (InstructorBaseRagasLLM) isn't a
# subclass of BaseRagasLLM, the interface every metric below requires --
# verified directly against the installed package rather than assumed.
# llm_factory targets a different (structured-output/Instructor) ragas
# workflow that these classic metric classes don't use.
#
# ragas==0.3.9 is pinned deliberately (backend/pyproject.toml): 0.4.3 (the
# latest release) has a hard import of a langchain-community submodule
# that was since removed upstream (langchain_community.chat_models.
# vertexai), breaking `import ragas` entirely regardless of which provider
# is actually used. Confirmed as a known, unfixed upstream bug, not a
# local misconfiguration.


class _EmbeddingProviderAdapter(Embeddings):
    """Wraps our own EmbeddingProvider (whichever one EMBEDDING_PROVIDER
    selects -- local, voyage, or fake) as a LangChain Embeddings, so RAGAS
    reuses the exact embeddings already configured for retrieval instead
    of needing its own separate provider and API key.
    """

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return get_embedding_provider().embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return get_embedding_provider().embed_query(text)


@lru_cache
def _build_llm() -> BaseRagasLLM:
    # Same provider (Anthropic) and model as the answer-generating LLM --
    # simplest setup (one API key) and cheapest, at the cost of a known,
    # named trade-off: a model judging its own family's output has a
    # documented self-preference bias in the evaluation literature. Worth
    # keeping in mind when reading scores, not a reason to avoid the
    # approach here.
    # timeout/stop: mypy's view of ChatAnthropic's pydantic-generated
    # __init__ marks these as required, but both are genuinely optional
    # at runtime (default=None per ChatAnthropic.model_fields) -- passed
    # explicitly as their real default, not a workaround.
    chat_model = ChatAnthropic(
        model_name=settings.LLM_MODEL,
        api_key=settings.ANTHROPIC_API_KEY,
        timeout=None,
        stop=None,
    )
    return LangchainLLMWrapper(chat_model)


@lru_cache
def _build_embeddings() -> BaseRagasEmbeddings:
    return LangchainEmbeddingsWrapper(_EmbeddingProviderAdapter())


def build_metrics() -> list[Metric]:
    """The four RAGAS metrics pinned in docs/learning-notes.md: context
    precision and context recall each judge retrieval (noise vs. gaps),
    faithfulness and answer relevancy each judge generation (grounded vs.
    hallucinated, on-topic vs. not) -- four separate signals precisely so
    a regression in one doesn't get averaged away by the other three.
    """
    llm = _build_llm()
    return [
        LLMContextPrecisionWithReference(llm=llm),
        LLMContextRecall(llm=llm),
        Faithfulness(llm=llm),
        ResponseRelevancy(llm=llm, embeddings=_build_embeddings()),
    ]


def build_sample(
    *, question: str, retrieved_contexts: list[str], response: str, reference: str
) -> SingleTurnSample:
    return SingleTurnSample(
        user_input=question,
        retrieved_contexts=retrieved_contexts,
        response=response,
        reference=reference,
    )


def run_evaluation(samples: Sequence[SingleTurnSample]):
    """Scores a batch of already-run pipeline turns against the four
    metrics. Building `samples` (running retrieval + the LLM for each
    golden-set question) is the caller's job -- this function only ever
    talks to the judge LLM, never to the pipeline under evaluation, so a
    test can fake the former without needing to fake the latter too.
    """
    # Explicitly widened, not just `list(samples)`: list is invariant, so
    # a list[SingleTurnSample] doesn't satisfy EvaluationDataset's
    # list[SingleTurnSample | MultiTurnSample] on its own -- this project
    # only ever builds SingleTurnSamples (see build_sample above), never
    # multi-turn ones.
    dataset_samples: list[SingleTurnSample | MultiTurnSample] = list(samples)
    dataset = EvaluationDataset(samples=dataset_samples)
    return evaluate(dataset, metrics=build_metrics())
