from django.urls import path
from . import views

urlpatterns=[
    path('create_task',views.create_task),
    path('register', views.register),
    path('tasks/<uuid:task_id>',views.task_info),
    path('tasks/<uuid:task_id>/attempts',views.task_attempts_info),
    path('tasks',views.task_list),
    path('tasks/<uuid:task_id>/retry',views.retry_task),
    path('tasks/<uuid:task_id>/cancel',views.cancel_task),
    path('workers/', views.worker_health),
    path('cancel_cron/<uuid:task_id>', views.cancel_cron),
    path('create_api_key', views.create_api_key),
    path('api_keys/', views.list_api_keys),
    path('api_keys/revoke/<int:api_key_id>', views.revoke_api_key),
]