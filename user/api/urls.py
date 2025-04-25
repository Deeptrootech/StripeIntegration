from django.urls import path
from knox import views as knox_views
from rest_framework.routers import SimpleRouter

from user.api.views import LoginView

app_name = "user_api"

router = SimpleRouter()


urlpatterns = router.urls

urlpatterns += [
    path("login/", LoginView.as_view(), name="knox_login"),
    path("logout/", knox_views.LogoutView.as_view(), name="knox_logout"),
    ]
