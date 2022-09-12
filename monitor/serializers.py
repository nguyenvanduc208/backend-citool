from rest_framework import serializers
from monitor.models import Task


class CreateTaskSerializer(serializers.ModelSerializer, serializers.Serializer):
    class Meta:
        model = Task
        fields = ("id", "url", "timestamp", "email", "sitename")
    url = serializers.CharField(max_length=255)
    timestamp = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False)
    id = serializers.CharField(max_length=255, required=False)
    email = serializers.ReadOnlyField(source='user.email')
    sitename = serializers.CharField(max_length=255, required=False)
