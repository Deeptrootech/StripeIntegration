from django.contrib.auth import login
from knox.views import LoginView as KnoxLoginView
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny

from user.api.serializers import AuthSerializer


class LoginView(KnoxLoginView, GenericAPIView):
    # login view extending KnoxLoginView
    serializer_class = AuthSerializer
    permission_classes = (AllowAny,)

    def post(self, request, format=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        login(request, user)
        response = super(LoginView, self).post(request, format=None)
        return super().post(request)
