from rest_framework import serializers

from .models import *

from django.contrib.auth.models import User
from rest_framework import serializers

#use this to recive the json data while creating the task
class TaskCreateSerializer(serializers.ModelSerializer):
    class Meta:
        #these type of serializer directly refer the models.py for reference rather than manually defining each attribute
        model=Task
        fields=[
            "callback_url",
            "method",
            "payload",
            "max_retries",
            "timeout",
            "scheduled_at",
            "cron_expression",
            "priority"
        ]

#use this to send the json data related to the task
class TaskResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model=Task
        fields=[
            "id",
            "callback_url",
            "method",
            "payload",
            "status",
            "created_at",
            "updated_at",
            "max_retries",
            "attempts",
            "timeout",
            "scheduled_at",
            "cron_expression",
            "parent_task",
            "priority",
            "retry_from"
        ]

#use this to send the json data related to the individual attempts
class TaskAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskAttempt
        fields = [
            "task",
            "attempt_number",
            "status",
            "response_status",
            "duration",
            "error",
            "created_at",
            "response_body"
        ]

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'password']

class APIKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = APIKey
        fields = ['id', 'name', 'suffix', 'is_active', 'created_at', 'revoked_at']
        read_only_fields = ['id', 'suffix', 'is_active', 'created_at', 'revoked_at']