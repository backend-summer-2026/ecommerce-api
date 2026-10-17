from rest_framework import generics, permissions, status
from rest_framework.response import Response

from .serializers import (
    ResendOTPSerializer,
    UserLoginSerializer,
    UserProfileSerializer,
    UserRegisterSerializer,
    VerifyOTPSerializer,
)


class RegisterAPIView(generics.GenericAPIView):
    """
    Register a new customer account.
    Creates an inactive user and sends a 6-digit OTP code to the provided email.
    """

    serializer_class = UserRegisterSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                'message': 'User registered successfully. A verification OTP code has been sent to your email.',
                'email': user.email,
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyOTPAPIView(generics.GenericAPIView):
    """
    Verify OTP code sent to user's email.
    Upon successful validation, activates user account and returns JWT tokens.
    """

    serializer_class = VerifyOTPSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(
            {
                'message': 'Account verified successfully.',
                'user': result['user'],
                'tokens': result['tokens'],
                'access': result['tokens']['access'],
                'refresh': result['tokens']['refresh'],
            },
            status=status.HTTP_200_OK,
        )


class ResendOTPAPIView(generics.GenericAPIView):
    """
    Resend OTP verification code to unverified user's email.
    Enforces a 60-second cooldown period between requests.
    """

    serializer_class = ResendOTPSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                'message': 'A new OTP verification code has been sent to your email.',
            },
            status=status.HTTP_200_OK,
        )


class LoginAPIView(generics.GenericAPIView):
    """
    Authenticate active user with email and password, returning JWT access and refresh tokens.
    """

    serializer_class = UserLoginSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.get_tokens()
        return Response(
            {
                'message': 'Login successful.',
                'user': result['user'],
                'tokens': result['tokens'],
                'access': result['tokens']['access'],
                'refresh': result['tokens']['refresh'],
            },
            status=status.HTTP_200_OK,
        )


class UserProfileAPIView(generics.RetrieveUpdateAPIView):
    """
    Retrieve or update profile details for the currently authenticated user.
    """

    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
