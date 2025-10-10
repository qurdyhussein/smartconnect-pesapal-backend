from django.urls import path
from .views import initiate_zenopay_payment, zenopay_webhook, check_zenopay_status, reset_password

urlpatterns = [
    path("zenopay/initiate/", initiate_zenopay_payment),
    path("zenopay/webhook/", zenopay_webhook),
    path("zenopay/status/<str:order_id>/", check_zenopay_status),
    path('reset-password/', reset_password),

]