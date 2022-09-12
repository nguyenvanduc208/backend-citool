from django.urls import path
from jmeter.views.session import SessionCreate, SessionDetail

urlpatterns = [
    path('task', SessionCreate.as_view()),
    path('task/<str:pk>', SessionDetail.as_view()),
]
