from django.db import models

# Create your models here.# bookings/models.py


class Booking(models.Model):
    reference = models.CharField(max_length=50, unique=True)  # e.g. SC1757573602806
    phone = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, default="PENDING")  # e.g. PENDING, COMPLETED, FAILED
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    confirmation_code = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
