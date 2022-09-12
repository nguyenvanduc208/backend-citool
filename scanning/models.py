import uuid
from django.contrib.auth.models import User
from django.db.models import \
    ForeignKey, Model, CharField, DateTimeField, DO_NOTHING, UUIDField, TextField, CASCADE, TimeField, DateField
from citool.const import STATUS_CHOICES


TYPE_CHOICES = [
    ('SAST', 'SAST'),
    ('DAST', 'DAST'),
]

LANGUAGE_CHOICES = [
    ('php', 'php'),
    ('java', 'java'),
    ('.net', '.net'),
    ('python', 'python'),
    ('eslint', 'eslint'),
    ('semgrep', 'semgrep'),
]

GIT_ENGINES = [
    ('github', 'github'),
    ('gitlab', 'gitlab'),
    ('bitbucket', 'bitbucket'),
]


class Sast(Model):
    git_engine = CharField(choices=GIT_ENGINES, default='gitlab', max_length=255)
    git_url = CharField(max_length=255)
    branch = CharField(max_length=255)
    run_type = CharField(choices=TYPE_CHOICES, max_length=255)
    timestamp = DateTimeField(auto_now_add=True)
    user = ForeignKey(User, on_delete=DO_NOTHING, null=True)

    class Meta:
        abstract = True
        managed = False


class Task(Sast):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = CharField(choices=STATUS_CHOICES, default='PENDING', max_length=255)

    class Meta:
        abstract = False
        managed = True


class SubTask(Model):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    language = CharField(choices=LANGUAGE_CHOICES, max_length=255)
    status = CharField(choices=STATUS_CHOICES, default='PENDING', max_length=255)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    task = ForeignKey(Task, on_delete=CASCADE, related_name='subtasks')


class Result(Model):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    description = TextField(max_length=1000)
    severity = CharField(max_length=255)
    file_path = TextField(max_length=1000)
    start_line = CharField(max_length=255, blank=True)
    link = TextField(max_length=1000, blank=True)
    note = TextField(max_length=10000, blank=True)
    subtask = ForeignKey(SubTask, on_delete=CASCADE, related_name='results')


class Schedule(Model):
    time = TimeField()
    day_of_week = CharField(max_length=255, blank=True)  # SUN,MON,TUE,WED,THU,FRI,SAT
    date = DateField(null=True)

    class Meta:
        abstract = True
        managed = False


class SastSchedule(Sast, Schedule):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    language = CharField(max_length=255)
    exclude_path = CharField(max_length=255, blank=True)

    class Meta:
        managed = True
