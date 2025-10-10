import os
import json
import requests
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
            print("🔥 Firebase connected successfully.")
        except Exception as e:
            print(f"❌ Error initializing Firebase: {e}")
    else:
        print("⚠️ FIREBASE_KEY not found in environment variables.")
firebase_db = firestore.client()


def update_booking_status(order_id, status_data):
    """
    ✅ Update transaction status directly in Firestore.
    Called automatically by Zenopay webhook or manual status check.
    """
    try:
        status = status_data.get("payment_status_description") or status_data.get("payment_status")
        method = status_data.get("payment_method")
        code = status_data.get("confirmation_code")
        channel = status_data.get("channel")
        transid = status_data.get("transid")

        if not firebase_db:
            print("⚠️ Firestore not initialized. Skipping update.")
            return

        doc_ref = firebase_db.collection("transactions").document(order_id)
        doc = doc_ref.get()

        update_data = {
            "status": status.upper() if status else "UNKNOWN",
            "payment_method": method,
            "confirmation_code": code,
            "channel": channel,
            "transid": transid,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        if doc.exists:
            doc_ref.update(update_data)
            print(f"✅ Transaction {order_id} updated to {status}")
        else:
            # If the transaction doesn't exist (maybe webhook came first)
            doc_ref.set({
                "order_id": order_id,
                **update_data,
                "created_at": firestore.SERVER_TIMESTAMP
            })
            print(f"🆕 Created new transaction {order_id} with status {status}")

    except Exception as e:
        print(f"🔥 Error updating Firestore transaction {order_id}: {e}")


def query_zenopay_payment_status(order_id):
    """
    ✅ Query Zenopay API manually and return payment result.
    """
    ZENOPAY_API_KEY = os.getenv("ZENOPAY_API_KEY")
    url = f"https://zenoapi.com/api/payments/order-status?order_id={order_id}"
    headers = {"x-api-key": ZENOPAY_API_KEY}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("result", "UNKNOWN")
    except Exception as e:
        print(f"❌ Error checking Zenopay status: {e}")
        return "ERROR"
