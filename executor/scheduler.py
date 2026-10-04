import os,time,django
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'taskmesh.settings')
django.setup()

from executor.models import Task
from executor.redis_client import redis_client

key="taskmesh:queue"

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

            redis_client.rpush(key,str(task.id))

            task.status=Task.Status.QUEUED

            print(f"task:{task.id} is queued")

            task.save()
