from unittest import result

from django.shortcuts import get_object_or_404, render
from .models import *
from .serializers import *
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes,authentication_classes
from .redis_client import redis_client
from django.utils import timezone
from croniter import croniter
from rest_framework.permissions import IsAuthenticated
import secrets,hashlib
from .authentication import APIKeyAuthentication


# Create your views here.
@api_view(["POST"])
@authentication_classes([APIKeyAuthentication])
def create_task(request):

    #recieve the task data from user->serialize->save it to db
    serializer=TaskCreateSerializer(data=request.data)

    if not serializer.is_valid():

        return Response({
            "messege":"Invalid data"
        },status=400)

    data=serializer.validated_data

    if (data.get("scheduled_at") and data["scheduled_at"] > timezone.now()) or data.get("cron_expression"):

        task=Task(callback_url=data["callback_url"],
            method=data["method"],
            payload=data["payload"],
            scheduled_at=data["scheduled_at"] if data.get("scheduled_at") else croniter(data["cron_expression"],timezone.now()).get_next(timezone.datetime),
            status=Task.Status.SCHEDULED,
            priority=data["priority"] if data.get("priority") else 2,
            owner=request.user
        )

        if "timeout" in data:
                task.timeout=data["timeout"]
        
        if "max_retries" in data:
                task.max_retries=data["max_retries"]

        if "cron_expression" in data:
                task.cron_expression=data["cron_expression"]
                task.parent_task=task

        task.save()

        return Response({
                "id":task.id,
                "status":task.status
            },status=200)


    task=Task(callback_url=data["callback_url"], 
        method=data["method"],
        payload=data["payload"],
        status=Task.Status.QUEUED,
        priority=data["priority"] if data.get("priority") else 2,
        owner=request.user
    )

    if "timeout" in data:
        task.timeout=data["timeout"]

    if "max_retries" in data:
        task.max_retries=data["max_retries"]

    task.save();

    #after saving the task, queue it(it's id) to redis
    redis_key=f"taskmesh:queue:{task.priority}"
    redis_data=str(task.id)
    redis_client.rpush(redis_key,redis_data)
    
    return Response({
        "id":task.id,
        "status":task.status
    },status=200)

#task info for a given task_id
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def task_info(request,task_id):

    task = get_object_or_404(Task,owner=request.user,id=task_id)  #returns the instance of Task where id=task_id or returns 404 if not found

    serializer = TaskResponseSerializer(task)   

    return Response(serializer.data)

#task attempts info for a given task_id
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def task_attempts_info(request,task_id):

    task = get_object_or_404(Task,owner=request.user,id=task_id)  #returns the instance of Task where id=task_id or returns 404 if not found

    attempts = TaskAttempt.objects.filter(task=task)  #get all the attempts related to the instance task of Task

    serializer = TaskAttemptSerializer(attempts, many=True)

    return Response(serializer.data)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def task_list(request):

    tasks=Task.objects.filter(owner=request.user).order_by('created_at')

    serializer=TaskResponseSerializer(tasks,many=True)

    return Response(serializer.data)

#retry the task if dead/failed
@api_view(["POST"])
@authentication_classes([APIKeyAuthentication])
def retry_task(request,task_id):

    task=get_object_or_404(Task,id=task_id)

    if task.status not in (Task.Status.DEAD, Task.Status.FAILED, Task.Status.CANCELLED):
        return Response({
            "message":"cannot retry task (not dead/failed/cancelled)"
        },status=400)

    new_task = Task.objects.create(
        callback_url=task.callback_url,
        method=task.method,
        payload=task.payload,
        timeout=task.timeout,
        max_retries=task.max_retries,
        priority=task.priority,
        status=Task.Status.QUEUED,
        retry_from=task
    )

    #repush the task into the redis queue
    redis_client.rpush(f"taskmesh:queue:{new_task.priority}", str(new_task.id))

    return Response({
        "id": new_task.id,
        "status": new_task.status
    })

@api_view(["POST"])
@authentication_classes([APIKeyAuthentication])
def cancel_task(request,task_id):

    task=get_object_or_404(Task,id=task_id)

    if task.status in [Task.Status.FAILED,Task.Status.DEAD,Task.Status.CANCELLED,Task.Status.SUCCESS]:

        return Response({
            "messege":"Task cannot be canceled"
        })

    #if is already running(popped from the queue) then set the redis flag to ping the worker to cancel
    if task.status!=Task.Status.QUEUED:

        cancel_key = f"taskmesh:cancel:{task.id}"

        redis_client.set(cancel_key, "1")

    #mark as cancelled 
    task.status=Task.Status.CANCELLED

    task.save()

    return Response({
        "id": str(task.id),
        "status": task.status
    })

@api_view(["GET"])
def worker_health(request):

     workers = Worker.objects.all()

     result = []

     for worker in workers:
            
            key = f"taskmesh:worker:{worker.worker_id}:heartbeat"
            is_healthy = redis_client.exists(key)
            last_seen = redis_client.get(key)

            result.append({
                 "id": str(worker.worker_id),
                 "registered_at": worker.registered_at,
                 "status": "HEALTHY" if is_healthy else "DEAD",
                 "last_seen": last_seen if last_seen else None
            })

     return Response(result)

@api_view(["POST"])
@authentication_classes([APIKeyAuthentication])
def cancel_cron(request,task_id):

    task=get_object_or_404(Task,id=task_id)

    if task.cron_expression is None:
            
            return Response({
                "message":"Task is not a cron job"
            },status=400)

    update_task=Task.objects.filter(parent_task=task,status=Task.Status.SCHEDULED).update(status=Task.Status.CANCELLED)

    if update_task==0:
        return Response({
            "message":f"cron job with parent task id {task_id} has already been terminated"
        })

    return Response({
        "message":f"cron job with parent task id {task_id} terminated successfully"
    })

@api_view(['POST'])
def register(request):
    serializer = RegisterSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    user = User.objects.create_user(**serializer.validated_data)

    return Response(
        {
            "message": "User registered successfully",
            "username": user.username
        },
        status=201
    )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_api_key(request):

    active_keys = APIKey.objects.filter(owner=request.user, is_active=True).count()

    if active_keys >= 10:
        return Response(
            {"message": "Maximum limit of 10 active API keys reached"},
            status=400
        )

    user = request.user

    data = request.data

    api_key = secrets.token_urlsafe(32)

    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    serializer_data = APIKeySerializer(data=data)

    if serializer_data.is_valid():

        APIKey.objects.create(owner=user,key_hash=key_hash,name=serializer_data.validated_data["name"], suffix=api_key[-8:])
        
        return Response({
            "message": "API key created successfully",
            "name": serializer_data.validated_data["name"],
            "key": api_key
        }, status=201)
    
    return Response(serializer_data.errors, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_api_keys(request):

    user = request.user

    api_keys = APIKey.objects.filter(owner=user)

    serializer = APIKeySerializer(api_keys, many=True)

    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def revoke_api_key(request, api_key_id):

    user = request.user

    api_key = get_object_or_404(APIKey, owner=user, id=api_key_id)

    if not api_key.is_active:
        return Response({
            "message": "API key is already revoked"
        }, status=400)

    api_key.is_active = False
    api_key.revoked_at = timezone.now()
    api_key.save()

    return Response({
        "message": "API key revoked successfully"
    })