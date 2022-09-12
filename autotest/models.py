from django.db import models
from django.contrib.auth.models import User
from rest_framework import serializers
import uuid
from citool.const import STATUS_CHOICES

TYPE_CHOICES = [
    ('SELENIUM', 'SELENIUM'),
]

BROWSER_CHOICES = [
    ('firefox', 'firefox'),
    ('chrome', 'chrome'),
    ('phantomjs', 'phantomjs'),
    ('edge chromiun', 'edge chromiun'),
    ('opera', 'opera')
]

# Create your models here.
class AutoTest(models.Model):
    git_url = models.CharField(max_length=255)
    branch = models.CharField(max_length=255)
    run_type = models.CharField(choices=TYPE_CHOICES, max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=True, related_name="user_set")

    class Meta:
        abstract = True
        managed = False


class Task(AutoTest):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(choices=STATUS_CHOICES, default='PENDING', max_length=255)

    class Meta:
        abstract = False
        managed = True


class SubTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    browser = models.CharField(choices=BROWSER_CHOICES, max_length=255)
    status = models.CharField(choices=STATUS_CHOICES, default='PENDING', max_length=255)
    log_group = models.CharField(max_length=255, default=None)
    log_stream = models.CharField(max_length=255, default=None)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='subtasks')
