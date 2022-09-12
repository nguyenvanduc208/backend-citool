import uuid
from django.contrib.auth.models import User
from django.db.models import Model, CharField, DateTimeField, UUIDField, ForeignKey, DO_NOTHING


class Task(Model):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = DateTimeField(auto_now_add=True)
    user = ForeignKey(User, on_delete=DO_NOTHING, null=True, related_name="monitor_task")
    url = CharField(max_length=255)
    sitename = CharField(max_length=255, blank=True)
