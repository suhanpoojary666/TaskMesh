from django.urls import path
from . import views

urlpatterns=[
    path('tasks',views.create_task),
    path('tasks/<uuid:task_id>',views.task_info),
    path('tasks/<uuid:task_id>/attempts',views.task_attempts_info)
]