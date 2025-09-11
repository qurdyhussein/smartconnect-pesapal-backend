# bookings/utils.py

from .models import Booking

def update_booking_status(reference, status_data):
    try:
        booking = Booking.objects.get(reference=reference)

        status = status_data.get("payment_status_description")
        method = status_data.get("payment_method")
        code = status_data.get("confirmation_code")

        # Avoid duplicate updates
        if booking.status == status:
            print(f"🔁 Booking {reference} already marked as {status}")
            return

        booking.status = status
        booking.payment_method = method
        booking.confirmation_code = code
        booking.save()

        print(f"✅ Booking {reference} updated to {status}")

    except Booking.DoesNotExist:
        print(f"⚠️ Booking with reference {reference} not found.")