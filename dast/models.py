import uuid
from django.contrib.auth.models import User
from django.db.models import \
    ForeignKey, Model, CharField, TextField, DateTimeField, UUIDField, CASCADE, BooleanField, FileField
from citool.const import STATUS_CHOICES


class Task(Model):
    def _get_upload_to(instance, filename):
        return '{}/wrk/{}'.format(instance.id, filename)

    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target_url = CharField(max_length=255, blank=True)
    full_scan = BooleanField(default=False)
    status = CharField(choices=STATUS_CHOICES, default='PENDING', max_length=10)
    s3_object = TextField(max_length=1000, blank=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    user = ForeignKey(User, on_delete=CASCADE, null=True, related_name="dast_task")
    filename = FileField(upload_to=_get_upload_to, null=True)


class Result(Model):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = ForeignKey(Task, on_delete=CASCADE, related_name='results')
    description = TextField(max_length=1000, blank=True)
    severity = CharField(max_length=255, blank=True)
    url = TextField(max_length=2000, blank=True)
    confidence = CharField(max_length=255, blank=True)
    message = TextField(max_length=2000, blank=True)
    solution = TextField(max_length=2000, blank=True)
    cve = CharField(max_length=255, blank=True)
    note = TextField(max_length=1000, blank=True)
    start_time = DateTimeField(null=True)
    end_time = DateTimeField(null=True)
