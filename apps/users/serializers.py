from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import OTPCode, User
from .services import can_request_new_otp, create_otp_for_user, send_otp_email


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for viewing and updating user profile information.
    """

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'phone_number',
            'role',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'email', 'role', 'created_at', 'updated_at']


class UserRegisterSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.
    Creates an inactive user (is_active=False) and sends an OTP code via email.
    """

    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
    )

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'phone_number',
            'password',
            'password_confirm',
        ]
        read_only_fields = ['id']

    def validate_email(self, value):
        normalized_email = value.lower().strip()
        user = User.objects.filter(email=normalized_email).first()
        if user:
            if user.is_active:
                raise serializers.ValidationError('A user with this email already exists.')
            # If user exists but is not active yet, we can delete the old inactive record
            # to allow re-registration fresh.
            user.delete()
        return normalized_email

    def validate(self, attrs):
        password = attrs.get('password')
        password_confirm = attrs.get('password_confirm')

        if password != password_confirm:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})

        validate_password(password)
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')

        user = User.objects.create_user(
            password=password,
            is_active=False,
            **validated_data,
        )

        # Generate and dispatch OTP
        otp_instance = create_otp_for_user(user, otp_type=OTPCode.OTPType.REGISTER)
        send_otp_email(user, otp_instance.code, otp_type=OTPCode.OTPType.REGISTER)

        return user


class VerifyOTPSerializer(serializers.Serializer):
    """
    Serializer for verifying registration OTP and activating the user account.
    """

    email = serializers.EmailField(required=True)
    code = serializers.CharField(required=True, max_length=6, min_length=6)

    def validate(self, attrs):
        email = attrs.get('email').lower().strip()
        code = attrs.get('code').strip()

        user = User.objects.filter(email=email).first()
        if not user:
            raise serializers.ValidationError({'email': 'User with this email not found.'})

        if user.is_active:
            raise serializers.ValidationError({'email': 'Account is already verified and active.'})

        otp = OTPCode.objects.filter(
            user=user,
            otp_type=OTPCode.OTPType.REGISTER,
            is_used=False,
        ).order_by('-created_at').first()

        if not otp:
            raise serializers.ValidationError({'code': 'No active verification code found. Please request a new one.'})

        if timezone.now() > otp.expires_at:
            raise serializers.ValidationError({'code': 'Verification code has expired. Please request a new one.'})

        if otp.code != code:
            raise serializers.ValidationError({'code': 'Invalid verification code.'})

        attrs['user'] = user
        attrs['otp'] = otp
        return attrs

    def save(self):
        user = self.validated_data['user']
        otp = self.validated_data['otp']

        # Activate user and consume OTP
        otp.is_used = True
        otp.save(update_fields=['is_used'])

        user.is_active = True
        user.save(update_fields=['is_active'])

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        return {
            'user': UserProfileSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
        }


class ResendOTPSerializer(serializers.Serializer):
    """
    Serializer for resending OTP code with cooldown enforcement.
    """

    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        normalized_email = value.lower().strip()
        user = User.objects.filter(email=normalized_email).first()
        if not user:
            raise serializers.ValidationError('No account found with this email.')
        if user.is_active:
            raise serializers.ValidationError('This account is already verified.')

        can_request, remaining = can_request_new_otp(user, otp_type=OTPCode.OTPType.REGISTER)
        if not can_request:
            raise serializers.ValidationError(
                f'Please wait {remaining} seconds before requesting a new code.'
            )

        self.context['user'] = user
        return normalized_email

    def save(self):
        user = self.context['user']
        otp_instance = create_otp_for_user(user, otp_type=OTPCode.OTPType.REGISTER)
        send_otp_email(user, otp_instance.code, otp_type=OTPCode.OTPType.REGISTER)
        return otp_instance


class UserLoginSerializer(serializers.Serializer):
    """
    Serializer for logging in with email and password.
    Returns JWT tokens and user profile if active.
    """

    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
    )

    def validate(self, attrs):
        email = attrs.get('email').lower().strip()
        password = attrs.get('password')

        user = authenticate(username=email, password=password)
        if not user:
            # Check if user exists but is inactive
            existing_user = User.objects.filter(email=email).first()
            if existing_user and not existing_user.is_active:
                raise serializers.ValidationError(
                    'Your email has not been verified yet. Please verify your OTP code to activate your account.'
                )
            raise serializers.ValidationError('Invalid email or password.')

        if not user.is_active:
            raise serializers.ValidationError(
                'Your email has not been verified yet. Please verify your OTP code to activate your account.'
            )

        attrs['user'] = user
        return attrs

    def get_tokens(self):
        user = self.validated_data['user']
        refresh = RefreshToken.for_user(user)
        return {
            'user': UserProfileSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
        }
