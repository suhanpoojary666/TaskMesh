import os,time,django

from django.utils import timezone
from django.db import transaction

#define django environtment for this process
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "taskmesh.settings")
django.setup()

from executor.models import Task,TaskAttempt
from executor.redis_client import redis_client

key="taskmesh:queue"


while True:

        now=timezone.now()

        expired_tasks = Task.objects.filter(
                status=Task.Status.RUNNING,
                lease__lte=now
            )

        for task in expired_tasks:

            with transaction.atomic():
                
                task=Task.objects.select_for_update().get(id=task.id)  #refresh queryset to get the latest status of the task

                attempt_count = TaskAttempt.objects.filter(task=task).count()

                if task.status != Task.Status.RUNNING or task.lease is None or task.lease > timezone.now():
                            continue  #recheck


                #attemps are remaining, requeue the task for execution
                if attempt_count < task.max_retries+1:

                    print(f"Task {task.id} has expired. Requeuing for execution.")

                    task.status=Task.Status.QUEUED

                    task.lease=None

                    task.save()

                    redis_client.rpush(key, str(task.id))

                # worker died when no more attempts were remaining, mark the task as DEAD
                else:

                    print(f"Task {task.id} has expired and no more attempts are remaining. Marking as DEAD.")

                    task.status=Task.Status.DEAD

                    task.lease=None

                    task.save()

        time.sleep(5)