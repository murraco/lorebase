from django.db import migrations

TITLE_MAX_LENGTH = 60


def backfill_titles(apps, schema_editor):
    """Names pre-existing conversations after their first user message.

    Conversation.title was always blank before rag.chat.service started
    setting it, which only mattered once the sidebar began listing past
    conversations — without this every existing one reads "Untitled".

    Also drops conversations that never got a single message: those are
    the residue of the frontend creating a Conversation eagerly on every
    /chat page load, which it no longer does. They have no content to
    lose by definition.
    """
    Conversation = apps.get_model("rag", "Conversation")

    for conversation in Conversation.objects.filter(title=""):
        first_message = conversation.messages.filter(role="user").order_by("created_at").first()
        if first_message is None:
            continue
        title = " ".join(first_message.content.split())
        if len(title) > TITLE_MAX_LENGTH:
            title = title[: TITLE_MAX_LENGTH - 1].rstrip() + "…"
        conversation.title = title
        conversation.save(update_fields=["title"])

    Conversation.objects.filter(messages__isnull=True).delete()


def noop_reverse(apps, schema_editor):
    """Deliberately not restoring blank titles: they carried no
    information, so "undoing" this would only destroy data.
    """


class Migration(migrations.Migration):
    dependencies = [("rag", "0001_initial")]

    operations = [migrations.RunPython(backfill_titles, noop_reverse)]
