from django.shortcuts import render
from .models import *
from .serializers import *
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .redis_client import redis_client


# Create your views here.

@api_view(["POST"])
def create_task(request):

    #recieve the task data from user->serialize->save it to db
    serializer=TaskCreateSerializer(data=request.data)

    if not serializer.is_valid():

        return Response({
            "messege":"Invalid data"
        },status=400)

    data=serializer.validated_data

    task=Task(callback_url=data["callback_url"],
        method=data["method"],
        payload=data["payload"])

    if "max_retries" in data:
        task.max_retries=data["max_retries"]

    task.save();

    #after saving the task, queue it(it's id) to redis
    redis_key="taskmesh:queue"
    redis_data=str(task.id)
    redis_client.rpush(redis_key,redis_data)
    
    return Response({
        "id":task.id,
        "status":task.status
    },status=200)




