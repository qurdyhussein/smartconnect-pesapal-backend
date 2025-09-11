from django.urls import path
from .views import get_token, submit_order_request, pesapal_ipn, check_payment_status

urlpatterns = [
    path("get-token/", get_token),
    path("submit-order-request/", submit_order_request),
    path("pesapal-ipn/", pesapal_ipn),
    path('check-payment-status/<str:reference>/', check_payment_status),
]