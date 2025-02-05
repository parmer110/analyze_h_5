from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('web_requests/', include('web_requests.urls')),
    path('schedule/', include('scheduler.urls')),
]
