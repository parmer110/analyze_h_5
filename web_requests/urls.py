from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SendSMSCodeViewSeHamkadeh, LoginViewSetHamkadeh, cm10, c_sup, run

router = DefaultRouter()
router.register(r'send-code', SendSMSCodeViewSeHamkadeh, basename='send-code')
router.register(r'login', LoginViewSetHamkadeh, basename='login')
router.register(r'cm10', cm10, basename='cm10')
router.register(r'c_sup', c_sup, basename='c_sup')

urlpatterns = [
    path('', include(router.urls)),
    path('run/', run, name="run_request"),
]