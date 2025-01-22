from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SendSMSCodeViewSeHamkadeh, LoginViewSetHamkadeh, cm10

router = DefaultRouter()
router.register(r'send-code', SendSMSCodeViewSeHamkadeh, basename='send-code')
router.register(r'login', LoginViewSetHamkadeh, basename='login')
router.register(r'cm10', cm10, basename='cm10')

urlpatterns = [
    path('', include(router.urls)),
]