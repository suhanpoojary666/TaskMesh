
import httpx
import os,django
import redis

#specify the django-setup for the standalone worker
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "taskmesh.settings")
django.setup()

from .redis_client import redis_client
from .models import Task


while True:
    try:
        task_id=redis_client.blpop('taskmesh:queue')[1]     #get task id from redis

        task=Task.objects.get(id=task_id)    #retrive the task info from database

        attempts = 0
        max_retries = task.max_retries
        print(max_retries)

        while task.status!=Task.Status.SUCCESS and attempts<max_retries:

            attempts=attempts+1

            try:

                response = httpx.request(      #execute the task
                    method=task.method,
                    url=task.callback_url,
                    json=task.payload
                    )
                
                if 200<=response.status_code<300:
                    task.status=Task.Status.SUCCESS

                else:
                    task.status=Task.Status.FAILED

            except:

                task.status=Task.Status.FAILED

        if task.status==Task.Status.FAILED:
            task.status=Task.Status.DEAD

        task.attempts=attempts
        print(f"Task {task.id} completed with status: {task.status} after {attempts} attempts.")
        task.save()

    except redis.exceptions.TimeoutError:
        continue #if there is not task redis times out after 5sec but the worker should continue