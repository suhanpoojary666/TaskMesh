from django.shortcuts import get_object_or_404, render
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

#task info for a given task_id
@api_view(["GET"])
def task_info(request,task_id):

    task = get_object_or_404(Task, id=task_id)  #returns the instance of Task where id=task_id or returns 404 if not found

    serializer = TaskResponseSerializer(task)   

    return Response(serializer.data)

#task attempts info for a given task_id
@api_view(["GET"])
def task_attempts_info(request,task_id):

    task = get_object_or_404(Task, id=task_id)  #returns the instance of Task where id=task_id or returns 404 if not found

    attempts = TaskAttempt.objects.filter(task=task)  #get all the attempts related to the instance task of Task

    serializer = TaskAttemptSerializer(attempts, many=True)

    return Response(serializer.data)

@api_view(["GET"])
def task_list(request):

    tasks=Task.objects.all().order_by('created_at')

    serializer=TaskResponseSerializer(tasks,many=True)

    return Response(serializer.data)

#retry the task if dead/failed
@api_view(["POST"])
def retry_task(request,task_id):

    task=get_object_or_404(Task,id=task_id)

    if task.status!=Task.Status.DEAD and task.status!=Task.Status.FAILED:
        return Response({
            "message":"cannot retry task (not dead/failed)"
        },status=400)

    #change the status to QUEUED
    task.status=Task.Status.QUEUED

    task.save();

    #repush the task into the redis queue
    redis_client.rpush("taskmesh:queue",str(task.id))

    return Response({
        "id": task.id,
        "status": task.status
    })
