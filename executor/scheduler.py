import os,time,django
from django.utils import timezone
import time
from croniter import croniter

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'taskmesh.settings')
django.setup()

from executor.models import Task
from executor.redis_client import redis_client

while True:
    
        now=timezone.now()

        #ORM query to get all the tasks which are scheduled for the current time and are in SCHEDULED status
        tasks=Task.objects.filter(
            scheduled_at__isnull=False,
            #lte means less than or equal to the current time(<=)
            scheduled_at__lte=now,
            status=Task.Status.SCHEDULED
        )

        for task in tasks:

            print(f"task:{task.id} is scheduled for execution")

            redis_client.rpush(f"taskmesh:queue:{task.priority}", str(task.id))

            task.status=Task.Status.QUEUED

            if task.cron_expression:

                  #next run time for the cron job
                  next_run = croniter(task.cron_expression,timezone.now()).get_next(timezone.datetime)

                  #continue the cron chain by new Task entry for next task run
                  Task.objects.create(
                      callback_url=task.callback_url,
                      method=task.method,
                      payload=task.payload,
                      scheduled_at=next_run,
                      status=Task.Status.SCHEDULED,
                      timeout=task.timeout,
                      max_retries=task.max_retries,
                      cron_expression=task.cron_expression,
                      parent_task=task.parent_task,
                      priority=task.priority
                  )

            print(f"task:{task.id} is queued")

            task.save()

        time.sleep(5)