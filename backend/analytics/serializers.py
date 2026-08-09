from rest_framework import serializers

from analytics.models import Feedback


class DailyQueryCountSerializer(serializers.Serializer):
    date = serializers.DateField()
    count = serializers.IntegerField()


class DashboardMetricsSerializer(serializers.Serializer):
    documents = serializers.IntegerField()
    queries_today = serializers.IntegerField()
    queries_by_day = DailyQueryCountSerializer(many=True)
    cost_this_month_usd = serializers.FloatField(allow_null=True)
    latency_p50_ms = serializers.IntegerField(allow_null=True)
    latency_p95_ms = serializers.IntegerField(allow_null=True)
    positive_feedback_percent = serializers.FloatField(allow_null=True)
    total_feedback = serializers.IntegerField()
    never_retrieved_documents = serializers.IntegerField()


class FeedbackSerializer(serializers.ModelSerializer):
    # `message` isn't in `fields`: it comes from the URL (which message
    # this feedback is for), never from the request body — the same
    # reasoning DRF's own docs give for excluding a parent id from a
    # nested resource's writable fields.
    class Meta:
        model = Feedback
        fields = ["id", "rating", "comment", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
