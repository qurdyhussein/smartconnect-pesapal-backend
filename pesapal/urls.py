from django.urls import path
from .views import get_token

urlpatterns = [
    path("get-token/", get_token),
]