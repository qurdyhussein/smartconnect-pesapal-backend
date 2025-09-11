from django.urls import path
from .views import get_token, submit_order_request

urlpatterns = [
    path("get-token/", get_token),
    path("submit-order-request/", submit_order_request),
]