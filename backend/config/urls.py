from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from core.api_views import SystemStatusView
from core.views import csrf_view, login_view, logout_view, me_view
from rag.chat.views import chat_stream_view
from rag.views import ConversationViewSet, MessageViewSet
from sources.views import DocumentViewSet, SourceViewSet

router = DefaultRouter()
router.register("sources", SourceViewSet, basename="source")
router.register("documents", DocumentViewSet, basename="document")
router.register("conversations", ConversationViewSet, basename="conversation")
router.register("messages", MessageViewSet, basename="message")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path(
        "api/conversations/<uuid:conversation_id>/chat/",
        chat_stream_view,
        name="chat-stream",
    ),
    path("api/system/status/", SystemStatusView.as_view(), name="system-status"),
    path("api/auth/csrf/", csrf_view, name="auth-csrf"),
    path("api/auth/me/", me_view, name="auth-me"),
    path("api/auth/login/", login_view, name="auth-login"),
    path("api/auth/logout/", logout_view, name="auth-logout"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]
