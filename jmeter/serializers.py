from rest_framework import serializers
from jmeter.models import Task


class SessionSerializers(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ("id", "loops", "num_threads", "ramp_time", "protocol", "domain", "port", "status", 
                  "run_type", "file", "report", "timestamp")
    status = serializers.CharField(source='get_status_display', required=False)
    timestamp = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False)
