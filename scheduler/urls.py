from django.urls import path
from .views import ScheduleRequestView

urlpatterns = [
    path('plan/', ScheduleRequestView.as_view(), name='plan')
]
