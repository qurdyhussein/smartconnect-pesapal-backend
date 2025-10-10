import os
import json
import requests
import firebase_admin
from firebase_admin import credentials, firestore

# 🔑 Initialize Firebase globally
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
        print(f"📦 Incoming status_data for {order_id}:", status_data)

        status = status_data.get("payment_status_description") or status_data.get("payment_status") or "UNKNOWN"
        method = status_data.get("payment_method") or "unspecified"
        code = status_data.get("confirmation_code") or status_data.get("reference") or "N/A"
        channel = status_data.get("channel") or "unknown"
        transid = status_data.get("transid") or status_data.get("transaction_id") or "pending"

        if not firebase_db:
            print("⚠️ Firestore not initialized. Skipping update.")
            return

        doc_ref = firebase_db.collection("transactions").document(order_id)
        doc = doc_ref.get()

        update_data = {
            "status": status.upper(),
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
    Also updates Firestore with fallback status and transid if available.
    """
    ZENOPAY_API_KEY = os.getenv("ZENOPAY_API_KEY")
    url = f"https://zenoapi.com/api/payments/order-status?order_id={order_id}"
    headers = {"x-api-key": ZENOPAY_API_KEY}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        print(f"📡 Zenopay status response for {order_id}:", data)

        raw_status = data.get("result", "UNKNOWN")
        details = data.get("data", [])
        payment_status = "UNKNOWN"
        transid = "pending"
        code = "N/A"
        method = "unspecified"
        channel = "unknown"

        if details and isinstance(details, list):
            first = details[0]
            if isinstance(first, dict):
                payment_status = first.get("payment_status") or "UNKNOWN"
                transid = first.get("transid") or first.get("transaction_id") or "pending"
                code = first.get("confirmation_code") or first.get("reference") or "N/A"
                method = first.get("payment_method") or "unspecified"
                channel = first.get("channel") or "unknown"

        normalized_status = (
            "COMPLETED" if payment_status == "COMPLETED"
            else "PENDING" if payment_status in ["PENDING", "INITIATED", "PROCESSING"]
            else "FAIL"
        )

        update_data = {
            "status": normalized_status,
            "transid": transid,
            "confirmation_code": code,
            "payment_method": method,
            "channel": channel,
            "checked_at": firestore.SERVER_TIMESTAMP
        }

        firebase_db.collection('transactions').document(order_id).update(update_data)
        print(f"✅ Fallback update for {order_id} → {normalized_status}")

        return {
            "order_id": order_id,
            "status": normalized_status,
            "transid": transid,
            "confirmation_code": code,
            "payment_method": method,
            "channel": channel,
            "details": details
        }

    except requests.exceptions.Timeout:
        print(f"⏳ Timeout while checking status for {order_id}")
        return {"order_id": order_id, "status": "UNKNOWN", "error": "Timeout"}
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error while checking status for {order_id}: {e}")
        return {"order_id": order_id, "status": "UNKNOWN", "error": str(e)}