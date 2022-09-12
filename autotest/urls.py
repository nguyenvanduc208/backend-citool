from django.urls import path
from autotest.views import AutotestDeleteAPIVIew, AutotestTaskLogRetrieve, AutotestAPIView, AutotestSubtaskAPIView


urlpatterns = [
    path('task', AutotestAPIView.as_view()),
    path('task/<str:pk>', AutotestDeleteAPIVIew.as_view()),
    path('subtask/<str:pk>', AutotestSubtaskAPIView.as_view()),
    path('logs/<str:pk>', AutotestTaskLogRetrieve.as_view())
]
