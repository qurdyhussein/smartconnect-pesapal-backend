from django.db import models

class Booking(models.Model):
    reference = models.CharField(max_length=50, unique=True)  # Zenopay order_id (UUID)
    phone = models.CharField(max_length=15)  # e.g. 0744963858
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # e.g. 12000.00
    status = models.CharField(max_length=20, default="PENDING")  # PENDING, COMPLETED, FAILED
    payment_method = models.CharField(max_length=50, blank=True, null=True)  # e.g. Zenopay, MPESA-TZ
    transaction_id = models.CharField(max_length=100, blank=True, null=True)  # Zenopay transid
    channel = models.CharField(max_length=50, blank=True, null=True)  # e.g. MPESA-TZ
    buyer_name = models.CharField(max_length=100, blank=True, null=True)  # e.g. Hussein M.
    buyer_email = models.EmailField(blank=True, null=True)  # e.g. hussein@smartconnect.tz
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.reference} - {self.status}"