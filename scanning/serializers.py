from rest_framework import serializers
from scanning.models import Task, SubTask, Result, SastSchedule, GIT_ENGINES
from citool.const import STATUS_CHOICES


class CreateTaskSerializer(serializers.ModelSerializer, serializers.Serializer):
    class Meta:
        model = Task
        fields = ("id", "git_url", "branch", "git_user", "status", "git_pass", "language", "owner", "exclude_path",
                  "run_type", "timestamp", "git_engine", "email")
    git_user = serializers.CharField(max_length=255, read_only=True)
    git_pass = serializers.CharField(max_length=255, read_only=True)
    language = serializers.CharField(max_length=255, read_only=True)
    owner = serializers.CharField(max_length=255, read_only=True)
    exclude_path = serializers.CharField(max_length=255, read_only=True)
    status = serializers.ChoiceField(choices=STATUS_CHOICES, required=False)
    git_engine = serializers.ChoiceField(choices=GIT_ENGINES, required=True)
    timestamp = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False)
    email = serializers.ReadOnlyField(source='user.email')


class ResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = Result
        fields = ("id", "description", "severity", "file_path", "start_line", "link", "note")

    id = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    severity = serializers.CharField(read_only=True)
    file_path = serializers.CharField(read_only=True)
    start_line = serializers.CharField(read_only=True)
    note = serializers.CharField(allow_blank=True)
    link = serializers.CharField(read_only=True)


class SubTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubTask
        fields = ("id", "language", "status", "created_at", "updated_at", "results")
    id = serializers.CharField(required=False)
    language = serializers.CharField(required=False)
    status = serializers.ChoiceField(choices=STATUS_CHOICES, required=False)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False)
    updated_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False)
    results = ResultSerializer(many=True, read_only=True)


class UpdateReceiveTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ("id", "git_url", "branch", "run_type", "status", "timestamp", "email", "subtasks")
    id = serializers.CharField(required=False)
    git_url = serializers.CharField(required=False)
    branch = serializers.CharField(required=False)
    run_type = serializers.CharField(required=False)
    status = serializers.ChoiceField(choices=STATUS_CHOICES, required=True)
    timestamp = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False)
    email = serializers.ReadOnlyField(source='user.email')
    subtasks = SubTaskSerializer(many=True, read_only=True)


class UpdateSubTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubTask
        fields = ("status",)
    status = serializers.ChoiceField(choices=STATUS_CHOICES, required=True)


class SastScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = SastSchedule
        fields = ("id", "git_engine", "git_url", "branch", "git_user", "git_pass", "language", "exclude_path", "time",
                  "run_type", "day_of_week", "timestamp", "email", "date")

    git_engine = serializers.CharField(max_length=255, required=True)
    git_user = serializers.CharField(max_length=255, read_only=True)
    git_pass = serializers.CharField(max_length=255, read_only=True)
    day_of_week = serializers.CharField(max_length=255, required=False)
    date = serializers.DateField(format="%Y-%m-%d", required=False)
    time = serializers.TimeField(format="%H:%M")
    timestamp = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False)
    email = serializers.ReadOnlyField(source='user.email')
