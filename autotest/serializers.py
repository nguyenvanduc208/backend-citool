from django.contrib.auth import models
from rest_framework import serializers
from autotest.models import Task, SubTask, STATUS_CHOICES

class AutoTestSerializer(serializers.ModelSerializer, serializers.Serializer):
    class Meta:
        model = Task
        fields = ("id", "git_url", "branch", "git_user", "status", "git_pass", "browser", "owner",
                  "run_type", "timestamp", "email", "sub_tasks")

    git_user = serializers.CharField(max_length=255, read_only=True)
    git_pass = serializers.CharField(max_length=255, read_only=True)
    browser = serializers.CharField(max_length=255, read_only=True)
    owner = serializers.CharField(max_length=255, read_only=True)
    status = serializers.ChoiceField(choices=STATUS_CHOICES, required=False)
    timestamp = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False)
    email = serializers.ReadOnlyField(source='user.email')
    sub_tasks = serializers.SerializerMethodField()

    def get_sub_tasks(self, instance):
        return self.context.get("sub_tasks")

class SubtaskSerializer(serializers.ModelSerializer, serializers.Serializer):
    class Meta:
        model = SubTask
        fields = ("status", "log_group", "log_stream")

    status = serializers.ChoiceField(choices=STATUS_CHOICES)
    log_group = serializers.CharField(max_length=255)
    log_stream = serializers.CharField(max_length=255)

class SubtaskResultSerializer(serializers.ModelSerializer, serializers.Serializer):
    class Meta:
        model = SubTask
        fields = ("id", "browser", "status", "created_at", "updated_at", "link")
    
    browser = serializers.CharField(max_length=255, read_only=True)
    link = serializers.SerializerMethodField()

    def get_link(self, instance):
        return self.context.get("link")

class SubtaskLogSerializer(serializers.ModelSerializer, serializers.Serializer):
    class Meta:
        model = SubTask
        fields = ("id", "browser", "status", "created_at", "updated_at", "results")

    results = serializers.SerializerMethodField()
    def get_results(self, instance):
        return self.context.get("results")

class AutotestLogTaskSerializer(serializers.ModelSerializer, serializers.Serializer):
    class Meta:
        model = Task
        fields = ("id", "git_url", "branch", "run_type", "status", "timestamp", "email", "sub_tasks")

    email = serializers.ReadOnlyField(source='user.email')
    sub_tasks = serializers.SerializerMethodField()
    timestamp = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False)

    def get_sub_tasks(self, instance):
        return self.context.get("sub_tasks")
