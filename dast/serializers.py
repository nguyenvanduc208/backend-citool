from rest_framework import serializers
from dast.models import Task, Result
from citool.const import STATUS_CHOICES


class CreateTaskSerializer(serializers.ModelSerializer, serializers.Serializer):
    class Meta:
        model = Task
        fields = ("id", "target_url", "full_scan", "dast_path", "status", "created_at", "updated_at", "scan_type",
                  "email", "filename", "target_type", "header_token")
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False)
    updated_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False)
    dast_path = serializers.CharField(allow_blank=True, read_only=True)
    scan_type = serializers.SerializerMethodField()
    email = serializers.ReadOnlyField(source='user.email')
    filename = serializers.FileField(required=False)
    target_url = serializers.CharField(max_length=255, required=False)
    target_type = serializers.SerializerMethodField()
    header_token = serializers.CharField(allow_blank=True, read_only=True)

    def get_scan_type(self, obj):
        if obj.full_scan:
            return "Full Scan"
        return "Quick Scan"

    def get_target_type(self, obj):
        if obj.filename:
            return "API"
        return "URL"


class ResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = Result
        fields = ("id", "description", "severity", "task", "url", "cve", "confidence", "message", "solution", "note",
                  "start_time", "end_time")

    id = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    severity = serializers.CharField(read_only=True)
    task = serializers.CharField(read_only=True)
    url = serializers.CharField(read_only=True)
    cve = serializers.CharField(allow_blank=True, required=False)
    confidence = serializers.CharField(allow_blank=True, required=False)
    message = serializers.CharField(allow_blank=True, required=False)
    solution = serializers.CharField(allow_blank=True, required=False)
    note = serializers.CharField(allow_blank=True, required=False)
    start_time = serializers.DateTimeField(format="%Y-%m-%dT%H:%M:%S", required=False)
    end_time = serializers.DateTimeField(format="%Y-%m-%dT%H:%M:%S", required=False)


class UpdateDestroyTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ("status",)
    status = serializers.ChoiceField(choices=STATUS_CHOICES, required=True)
