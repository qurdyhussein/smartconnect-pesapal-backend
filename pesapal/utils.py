import os
import json
import requests
from .models import Booking

import firebase_admin
from firebase_admin import credentials, firestore

# ✅ Initialize Firebase once globally
if not firebase_admin._apps:
    firebase_key_json = os.getenv("FIREBASE_KEY")

    if firebase_key_json:
        try:
            cred_dict = json.loads(firebase_key_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            db = firestore.client()
            print("🔥 Firebase connected successfully.")
        except Exception as e:
            print(f"❌ Error initializing Firebase: {e}")
            db = None
    else:
        print("⚠️ FIREBASE_KEY not found in environment variables.")
        db = None
else:
    db = firestore.client()

def update_booking_status(reference, status_data):
    try:
        booking = Booking.objects.get(reference=reference)

        status = status_data.get("payment_status_description")
        method = status_data.get("payment_method")
        code = status_data.get("confirmation_code")
        channel = status_data.get("channel")
        transid = status_data.get("transid")

        # Avoid duplicate updates
        if booking.status == status:
            print(f"🔁 Booking {reference} already marked as {status}")
            return

        booking.status = status
        booking.payment_method = method
        booking.transaction_id = transid or code
        booking.channel = channel
        booking.save()

        print(f"✅ Booking {reference} updated to {status}")

        # 🔥 Sync to Firestore (optional but powerful)
        if db:
            try:
                doc_ref = db.collection("bookings").document(reference)
                doc_ref.set({
                    "reference": reference,
                    "status": status,
                    "payment_method": method,
                    "transaction_id": transid or code,
                    "channel": channel,
                }, merge=True)
                print(f"📡 Firestore updated for booking {reference}")
            except Exception as e:
                print(f"⚠️ Error writing to Firestore: {e}")
        else:
            print("⚠️ Firestore not initialized, skipping sync.")

    except Booking.DoesNotExist:
        print(f"⚠️ Booking with reference {reference} not found.")

def query_zenopay_payment_status(reference):
    booking = Booking.objects.filter(reference=reference).first()
    if not booking:
        return "not_found"

    ZENOPAY_API_KEY = os.getenv("ZENOPAY_API_KEY")
    url = f"https://zenoapi.com/api/payments/order-status?order_id={reference}"
    headers = {
        "x-api-key": ZENOPAY_API_KEY
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("result", "UNKNOWN")
    except Exception as e:
        print(f"❌ Error checking Zenopay status: {e}")
        return "error"
