from django.urls import path
from monitor.views import TaskListCreate, TaskRetrieveDestroyStatus, GetResponseTime

urlpatterns = [
    path('task', TaskListCreate.as_view()),
    path('task/<str:pk>', TaskRetrieveDestroyStatus.as_view()),
    path('response/<str:pk>', GetResponseTime.as_view()),
]
