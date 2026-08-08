from rest_framework import serializers


class ProviderStatusSerializer(serializers.Serializer):
    provider = serializers.CharField()
    model = serializers.CharField()


class SystemStatusSerializer(serializers.Serializer):
    embedding = ProviderStatusSerializer()
    reranking = ProviderStatusSerializer()
    llm = ProviderStatusSerializer()
    embedding_dimensions = serializers.IntegerField()
    retrieval_strategy = serializers.CharField()
    sources = serializers.IntegerField()
    documents = serializers.IntegerField()
    chunks = serializers.IntegerField()
    embedded_chunks = serializers.IntegerField()
    answers = serializers.IntegerField()
    avg_latency_ms = serializers.IntegerField(allow_null=True)
    avg_citations_per_answer = serializers.FloatField(allow_null=True)
    ungrounded_answers = serializers.IntegerField()
    using_fake_providers = serializers.BooleanField()
