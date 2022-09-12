from django.urls import path
from dast.views import TaskListCreate, RetrieveResult, DowloadObject, ResultUpdate, TaskRetrieveDestroy
urlpatterns = [
    path('task', TaskListCreate.as_view()),
    path('task/<str:pk>', TaskRetrieveDestroy.as_view()),
    path('download/<str:pk>', DowloadObject.as_view()),
    path('result/<str:pk>', RetrieveResult.as_view()),
]
