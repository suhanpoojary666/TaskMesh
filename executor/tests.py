from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from .models import Task, TaskAttempt


class RetryTaskTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.task = Task.objects.create(
            callback_url="https://example.com/task",
            method="PUT",
            payload={"work": "example"},
            status=Task.Status.FAILED,
            attempts=2,
            max_retries=5,
            timeout=30,
            priority=1,
        )
        self.attempt = TaskAttempt.objects.create(
            task=self.task,
            attempt_number=2,
            status=Task.Status.FAILED,
        )

    @patch("executor.views.redis_client.rpush")
    def test_retry_creates_and_queues_new_task(self, rpush):
        response = self.client.post(f"/tasks/{self.task.id}/retry")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Task.objects.count(), 2)
        new_task = Task.objects.exclude(id=self.task.id).get()

        self.assertNotEqual(new_task.id, self.task.id)
        self.assertEqual(new_task.status, Task.Status.QUEUED)
        self.assertEqual(new_task.attempts, 0)
        self.assertEqual(new_task.callback_url, self.task.callback_url)
        self.assertEqual(new_task.method, self.task.method)
        self.assertEqual(new_task.payload, self.task.payload)
        self.assertEqual(new_task.timeout, self.task.timeout)
        self.assertEqual(new_task.max_retries, self.task.max_retries)
        self.assertEqual(new_task.priority, self.task.priority)

        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.FAILED)
        self.assertEqual(self.task.attempts, 2)
        self.assertTrue(TaskAttempt.objects.filter(id=self.attempt.id).exists())
        rpush.assert_called_once_with(
            f"taskmesh:queue:{new_task.priority}",
            str(new_task.id),
        )
        self.assertEqual(response.data["id"], new_task.id)

    @patch("executor.views.redis_client.rpush")
    def test_retry_rejects_task_that_is_not_terminal(self, rpush):
        self.task.status = Task.Status.QUEUED
        self.task.save(update_fields=["status"])

        response = self.client.post(f"/tasks/{self.task.id}/retry")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Task.objects.count(), 1)
        rpush.assert_not_called()
