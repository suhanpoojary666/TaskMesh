
import httpx
import os,django
import redis,time

#specify the django-setup for the standalone worker
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "taskmesh.settings")
django.setup()

from .redis_client import redis_client
from .models import Task,TaskAttempt

while True:
    try:
        task_id=redis_client.blpop('taskmesh:queue')[1]     #get task id from redis

        task=Task.objects.get(id=task_id)    #retrive the task info from database

        task.status=Task.Status.RUNNING

        task.save()

        #task has been cancelled, skip the execution
        if task.status == Task.Status.CANCELLED:
            print(f"Task {task.id} was cancelled. Skipping.")
            continue

        cancel_key = f"taskmesh:cancel:{task.id}"

        attempts = 0
        max_retries = task.max_retries
        print(max_retries)

        while task.status!=Task.Status.SUCCESS and attempts<max_retries:

            #check if the task has been cancelled through redis flag
            if redis_client.get(cancel_key):
                        print(f"Task {task.id} was cancelled. Skipping.")
                        task.status = Task.Status.CANCELLED
                        redis_client.delete(cancel_key)
                        break
            
            attempts=attempts+1
            attempt_start_time=time.perf_counter()  #record the attempt start time

            try:

                response = httpx.request(      #execute the task
                    method=task.method,
                    url=task.callback_url,
                    json=task.payload
                    )
                
                if 200<=response.status_code<300:
                    task.status=Task.Status.SUCCESS

                    #register the attempt info
                    TaskAttempt.objects.create(
                        task=task,
                        attempt_number=attempts,
                        status="SUCCESS",
                        response_status=response.status_code,
                        error=None,
                        duration=time.perf_counter()-attempt_start_time 
                    )

                else:
                    task.status=Task.Status.FAILED

                    #register the attempt info
                    TaskAttempt.objects.create(
                        task=task,
                        attempt_number=attempts,
                        status="FAILED",
                        response_status=response.status_code,
                        error=None,
                        duration=time.perf_counter()-attempt_start_time 
                    )

                    delay=2**(attempts)   #exponential delay after every attempt
                    time.sleep(delay)
                    print(f"attempt={attempts} with delay={delay}")

            except Exception as e:

                task.status=Task.Status.FAILED

                #register the attempt info
                TaskAttempt.objects.create(
                    task=task,
                    attempt_number=attempts,
                    status="FAILED",
                    response_status=None,
                    error=str(e),
                    duration=time.perf_counter()-attempt_start_time 
                )

                delay=2**(attempts)   #exponential delay after every attempt
                time.sleep(delay)
                print(f"attempt={attempts} with delay={delay}")

        if task.status==Task.Status.FAILED:
            task.status=Task.Status.DEAD

        task.attempts=attempts
        print(f"Task {task.id} completed with status: {task.status} after {attempts} attempts.")
        task.save()

    except redis.exceptions.TimeoutError:
        continue #if there is not task redis times out after 5sec but the worker should continue