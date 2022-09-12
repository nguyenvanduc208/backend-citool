import uuid
from django.contrib.auth.models import User
from django.db.models import \
    ForeignKey, Model, CharField, TextField, DateTimeField, UUIDField, CASCADE
from citool.const import STATUS_CHOICES


class Task(Model):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    git_url = CharField(max_length=255)
    branch = CharField(max_length=255)
    compared_branch1 = CharField(max_length=255, blank=True)
    compared_branch2 = CharField(max_length=255, blank=True)
    commit_id1 = CharField(max_length=255, blank=True)
    commit_id2 = CharField(max_length=255, blank=True)
    include_lang = CharField(max_length=255, blank=True)
    exclude_dir = TextField(max_length=1000, blank=True)
    status = CharField(choices=STATUS_CHOICES, default='PENDING', max_length=255)
    s3_object = TextField(max_length=1000, blank=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    user = ForeignKey(User, on_delete=CASCADE, null=True, related_name="cloc_task")


class Result(Model):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = CharField(max_length=255)
    files = CharField(max_length=255)
    blank = CharField(max_length=255)
    comment = CharField(max_length=255)
    code = CharField(max_length=255)
    task = ForeignKey(Task, on_delete=CASCADE, related_name='results')
    action = CharField(max_length=255)
    tittle = CharField(max_length=255)
    language = CharField(max_length=255)
