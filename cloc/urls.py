from django.urls import path
from cloc.views import TaskListCreate, TaskRetrieveDestroy, DowloadObject, ResultView
urlpatterns = [
    path('task', TaskListCreate.as_view()),
    path('task/<str:pk>', TaskRetrieveDestroy.as_view()),
    path('download/<str:pk>', DowloadObject.as_view()),
    path('result/<str:pk>', ResultView.as_view()),
]
