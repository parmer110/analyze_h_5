from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SendSMSCodeViewSeHamkadeh, LoginViewSetHamkadeh, LoginViewSet5040, RefreshSessionViewSet5040, LogoutViewSet5040,
    cm10, c_sup,
    run, 
)

router = DefaultRouter()
router.register(r'h/send-code', SendSMSCodeViewSeHamkadeh, basename='send-code-h')
router.register(r'h/login', LoginViewSetHamkadeh, basename='login-h')
router.register(r'h/cm10', cm10, basename='cm10')
router.register(r'h/c_sup', c_sup, basename='c_sup')

router.register(r'5/login', LoginViewSet5040, basename='login-5')
router.register(r'5/logout', LogoutViewSet5040, basename='logout-5')



urlpatterns = [
    path('', include(router.urls)),
    path('run/', run, name="run_request"),
     path('5/refresh/', RefreshSessionViewSet5040.as_view({'get': 'refresh_5'})),
]