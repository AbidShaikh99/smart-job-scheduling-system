
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from utils.responses import error_response, success_response
from .serializers import LoginSerializer, RegisterSerializer


class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if not serializer.is_valid():
            return error_response(
                message="Validation failed.",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Public registration always creates a Customer.
        user = serializer.save(role="CUSTOMER")

        return success_response(
            message="Registration successful.",
            data={
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role,
            },
            status_code=status.HTTP_201_CREATED,
        )


class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return error_response(
                message="Login failed.",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)

        return success_response(
            message="Login successful.",
            data={
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.role,
                },
            },
            status_code=status.HTTP_200_OK,
        )


class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not isinstance(refresh_token, str) or not refresh_token.strip():
            return error_response(
                message="Refresh token is required.",
                data={"refresh": ["This field is required."]},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)

            if str(token["user_id"]) != str(request.user.pk):
                return error_response(
                    message="This refresh token does not belong to you.",
                    status_code=status.HTTP_403_FORBIDDEN,
                )

            token.blacklist()

            return success_response(
                message="Logout successful.",
                status_code=status.HTTP_200_OK,
            )

        except TokenError:
            return error_response(
                message="Invalid or expired refresh token.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )