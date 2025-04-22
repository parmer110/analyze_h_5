from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include("common.urls")),
    path('web_requests/', include('web_requests.urls')),
    path('schedule/', include('scheduler.urls')),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
