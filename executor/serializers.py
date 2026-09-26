from rest_framework import serializers

from .models import Task

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
        ]