from django.urls import path
from . import views

urlpatterns=[
    path('create_task',views.create_task),
    path('tasks/<uuid:task_id>',views.task_info),
    path('tasks/<uuid:task_id>/attempts',views.task_attempts_info),
    path('tasks',views.task_list),
    path('tasks/<uuid:task_id>/retry',views.retry_task)
]