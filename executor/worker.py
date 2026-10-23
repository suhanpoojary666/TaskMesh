import httpx
import os,django
import redis,time
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
import uuid
import threading

#specify the django-setup for the standalone worker
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "taskmesh.settings")
django.setup()

from .redis_client import redis_client
from .models import Task,TaskAttempt,Worker

worker_id = str(uuid.uuid4())  #generate a unique id for the each worker instance
heartbeat_key = f"taskmesh:worker:{worker_id}:heartbeat"

# Register the worker
Worker.objects.create(worker_id=worker_id);
print(f"Worker {worker_id} registered.")


#heart-beat function that runs as a seperate thread in worker process
def send_heartbeat():
    while True:
        try:
            redis_client.set(
                heartbeat_key,
                timezone.now().isoformat(),
                ex=30
            )
        except Exception as e:
            print(f"Heartbeat failed: {e}")

        time.sleep(10)

#start the heart-beat thread
threading.Thread(target=send_heartbeat, daemon=True).start()


while True:
    try:
        task_id=redis_client.blpop('taskmesh:queue')[1]     #get task id from redis

        with transaction.atomic():

                task = Task.objects.select_for_update().get(id=task_id)    #retrive the task info from database and locks it from other workers(atomic transaction)

                if task.status==Task.Status.CANCELLED or task.status==Task.Status.SUCCESS  or task.status==Task.Status.RUNNING:
                    continue  #if the task was cancelled

                #lock the task for execution by this worker
                total_time = (task.max_retries + 1) * task.timeout + (2 ** (task.max_retries + 2) - 2)   #this time includes total time for all attempts(worst=timeout)+total exponential backoff time
                lease = total_time + 30
                task.lease =timezone.now()+timedelta(seconds=lease) #the worker can have the lock for the calculated lease duration

                task.status=Task.Status.RUNNING

                task.save()

        cancel_key = f"taskmesh:cancel:{task.id}"

        attempts = TaskAttempt.objects.filter(task=task).count()    #retuns the number of logs for this task in taskattempt table
        max_retries = task.max_retries
        print(f"max_retries= {max_retries}")

        while task.status!=Task.Status.SUCCESS and attempts<max_retries+1:

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
                    json=task.payload,
                    timeout=task.timeout
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
                        duration=time.perf_counter() - attempt_start_time,
                        response_body=response.text if response.text else None,
                    )
                    print(f"LOG CREATED: task={task.id}, attempt={attempts}")

                else:
                    task.status=Task.Status.FAILED

                    #register the attempt info
                    TaskAttempt.objects.create(
                        task=task,
                        attempt_number=attempts,
                        status="FAILED",
                        response_status=response.status_code,
                        error=None,
                        duration=time.perf_counter() - attempt_start_time,
                        response_body=None,
                    )

                    delay=2**(attempts)   #exponential delay after every attempt
                    print(f"attempt={attempts} with delay={delay}")
                    time.sleep(delay)
                    

            except Exception as e:
                task.status=Task.Status.FAILED

                #register the attempt info
                TaskAttempt.objects.create(
                    task=task,
                    attempt_number=attempts,
                    status="FAILED",
                    response_status=None,
                    error=str(e),
                    duration=time.perf_counter() - attempt_start_time,
                    response_body=None,
                )
                delay=2**(attempts)   #exponential delay after every attempt
                print(f"attempt={attempts} with delay={delay}")
                time.sleep(delay)
                

        if task.status==Task.Status.FAILED:
            task.status=Task.Status.DEAD

        task.attempts=attempts
        task.lease=None  #release the lock on the task
        print(f"Task {task.id} completed with status: {task.status} after {attempts} attempts.")
        task.save()

    except redis.exceptions.TimeoutError:
        continue #if there is not task redis times out after 5sec but the worker should continue