from rest_framework import serializers
from cloc.models import Task, Result
from citool.const import STATUS_CHOICES


class CreateTaskSerializer(serializers.ModelSerializer, serializers.Serializer):
    class Meta:
        model = Task
        fields = ("id", "git_url", "branch", "compared_branch1", "compared_branch2", "git_user", "git_pass", "status",
                  "created_at", "updated_at", "include_lang", "exclude_dir", "email", "commit_id1", "commit_id2")

    git_user = serializers.CharField(max_length=255, read_only=True)
    git_pass = serializers.CharField(max_length=255, read_only=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False)
    updated_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False)
    email = serializers.ReadOnlyField(source='user.email')
    commit_id1 = serializers.CharField(max_length=255, required=False)
    commit_id2 = serializers.CharField(max_length=255, required=False)
    compared_branch1 = serializers.CharField(max_length=255, required=False)
    compared_branch2 = serializers.CharField(max_length=255, required=False)


class UpdateDestroyTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ("status",)
    status = serializers.ChoiceField(choices=STATUS_CHOICES, required=True)


class ResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = Result
        fields = ("name", "files", "blank", "comment", "code", "action", "tittle", "language")
