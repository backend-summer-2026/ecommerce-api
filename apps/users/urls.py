from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    LoginAPIView,
    RegisterAPIView,
    ResendOTPAPIView,
    UserProfileAPIView,
    VerifyOTPAPIView,
)

app_name = 'users'

urlpatterns = [
    path('register/', RegisterAPIView.as_view(), name='register'),
    path('verify-otp/', VerifyOTPAPIView.as_view(), name='verify-otp'),
    path('resend-otp/', ResendOTPAPIView.as_view(), name='resend-otp'),
    path('send-otp/', ResendOTPAPIView.as_view(), name='send-otp'),
    path('login/', LoginAPIView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('me/', UserProfileAPIView.as_view(), name='profile-me'),
]
