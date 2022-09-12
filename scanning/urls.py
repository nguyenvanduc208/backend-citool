from django.urls import path
from scanning.views.task import TaskListCreate, TaskRetrieveDestroy, SubTaskUpdate, SastScheduleListCreate, \
    ResultUpdate, SastScheduleDelete
from scanning.views.dashboard import RecentRun, OverView

urlpatterns = [
    path('task', TaskListCreate.as_view()),
    path('task/<str:pk>', TaskRetrieveDestroy.as_view()),
    path('subtask/<str:pk>', SubTaskUpdate.as_view()),
    path('result/<str:pk>', ResultUpdate.as_view()),
    path('schedule', SastScheduleListCreate.as_view()),
    path('schedule/<str:pk>', SastScheduleDelete.as_view()),
    path('overview', OverView.as_view()),
    path('recent', RecentRun.as_view()),
]
