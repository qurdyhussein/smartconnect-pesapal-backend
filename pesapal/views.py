import os
import uuid
import json
import requests
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import JsonResponse
from .utils import update_booking_status
import firebase_admin
from firebase_admin import credentials, firestore

# 🔑 Init Firebase
if not firebase_admin._apps:
    cred_path = os.environ.get("FIREBASE_KEY_PATH", "/etc/secrets/firebase.json")
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    else:
        firebase_admin.initialize_app()
db = firestore.client()

# 🔑 Env keys
ZENOPAY_API_KEY = os.environ.get("ZENOPAY_API_KEY")
WEBHOOK_SECRET = os.environ.get("ZENOPAY_WEBHOOK_SECRET", ZENOPAY_API_KEY)  # fallback

# 🧾 Step 1: Initiate Zenopay Payment
@api_view(['POST'])
def initiate_zenopay_payment(request):
    try:
        data = request.data
        phone = data.get("phone")
        amount = data.get("amount")
        buyer_name = data.get("buyer_name", "SmartConnect User")
        buyer_email = data.get("buyer_email", "user@smartconnect.tz")
        customer_id = data.get("customer_id", "unknown")

        if not phone or not amount:
            return Response({"error": "Missing phone or amount"}, status=400)

        try:
            amount = int(amount)
        except (ValueError, TypeError):
            return Response({"error": "Invalid amount"}, status=400)

        order_id = str(uuid.uuid4())

        # ✅ Save transaction to Firestore
        db.collection('transactions').document(order_id).set({
            "order_id": order_id,
            "phone": phone,
            "amount": amount,
            "buyer_name": buyer_name,
            "buyer_email": buyer_email,
            "customer_id": customer_id,
            "status": "INITIATED",
            "created_at": firestore.SERVER_TIMESTAMP
        })

        headers = {
            "Content-Type": "application/json",
            "x-api-key": ZENOPAY_API_KEY
        }

        payload = {
            "order_id": order_id,
            "buyer_email": buyer_email,
            "buyer_name": buyer_name,
            "buyer_phone": phone,
            "amount": amount,
            "webhook_url": "https://smartconnect-pesapal-api.onrender.com/api/zenopay/webhook/"
        }

        res = requests.post(
            "https://zenoapi.com/api/payments/mobile_money_tanzania",
            headers=headers,
            json=payload,
            timeout=15
        )

        try:
            response_data = res.json()
        except ValueError:
            response_data = {"raw_response": res.text}

        if res.status_code != 200:
            db.collection('transactions').document(order_id).update({
                "status": "FAILED",
                "error": response_data
            })
            return Response({
                "error": f"Zenopay returned {res.status_code}",
                "response": response_data
            }, status=res.status_code)

        db.collection('transactions').document(order_id).update({
            "status": "PENDING",
            "zenopay_response": response_data
        })

        return Response({
            "status": "initiated",
            "order_id": order_id,
            "zenopay_response": response_data
        })

    except Exception as e:
        print("🔥 Initiate error:", str(e))
        return Response({"error": str(e)}, status=500)

# 📡 Step 2: Webhook Handler
@csrf_exempt
@api_view(['POST'])
def zenopay_webhook(request):
    try:
        incoming_key = request.headers.get("x-api-key")
        print("🔐 Incoming x-api-key:", incoming_key)

        if incoming_key != WEBHOOK_SECRET and incoming_key is not None:
            print("❌ Webhook rejected: invalid x-api-key")
            return Response({"error": "Unauthorized webhook"}, status=403)

        try:
            data = json.loads(request.body)
        except ValueError:
            return Response({"error": "Invalid JSON"}, status=400)

        order_id = data.get("order_id")
        status = data.get("payment_status_description") or data.get("payment_status")
        method = data.get("payment_method")
        code = data.get("confirmation_code") or data.get("reference")
        channel = data.get("channel")
        transid = data.get("transid")

        if not order_id or not status:
            return Response({"error": "Missing order_id or payment_status"}, status=400)

        update_booking_status(order_id, {
            "payment_status_description": status,
            "payment_method": method,
            "confirmation_code": code,
            "channel": channel,
            "transid": transid
        })

        transaction_ref = db.collection('transactions').document(order_id)
        transaction_ref.update({
            "status": status.upper(),
            "payment_method": method,
            "confirmation_code": code,
            "channel": channel,
            "transid": transid,
            "updated_at": firestore.SERVER_TIMESTAMP
        })

        # ✅ Voucher assignment if payment is completed
        if status.upper() == "COMPLETED":
            transaction_doc = transaction_ref.get()
            customer_id = transaction_doc.to_dict().get("customer_id")

            voucher_query = db.collection('vouchers').where('status', '==', 'available').limit(1).stream()
            voucher_doc = next(voucher_query, None)

            if voucher_doc:
                voucher_id = voucher_doc.id
                voucher_ref = db.collection('vouchers').document(voucher_id)

                voucher_ref.update({
                    'assigned_to': customer_id,
                    'status': 'assigned',
                    'assigned_at': firestore.SERVER_TIMESTAMP
                })

                transaction_ref.update({
                    'assigned_voucher': voucher_id,
                    'assigned_at': firestore.SERVER_TIMESTAMP
                })

                print(f"🎁 Voucher {voucher_id} assigned to {customer_id}")

        print(f"✅ Webhook processed for order {order_id} - {status}")
        return Response({"status": "received", "order_id": order_id})

    except Exception as e:
        print("🔥 Webhook error:", str(e))
        return Response({"error": "Internal server error"}, status=500)

# ✅ Step 3: Manual Status Check
@api_view(['GET'])
def check_zenopay_status(request, order_id):
    headers = {
        "x-api-key": ZENOPAY_API_KEY
    }

    url = f"https://zenoapi.com/api/payments/order-status?order_id={order_id}"
    attempts = 0
    max_attempts = 3
    last_error = None

    while attempts < max_attempts:
        try:
            res = requests.get(url, headers=headers, timeout=10)
            try:
                status_data = res.json()
            except ValueError:
                status_data = {"raw_response": res.text}

            raw_status = status_data.get("result")
            details = status_data.get("data", [])
            payment_status = None
            if details and isinstance(details, list):
                first = details[0]
                if isinstance(first, dict):
                    payment_status = first.get("payment_status")

            if raw_status == "SUCCESS" and payment_status == "COMPLETED":
                normalized_status = "COMPLETED"
            elif payment_status in ["PENDING", "INITIATED", "PROCESSING"]:
                normalized_status = "PENDING"
            else:
                normalized_status = "FAIL"

            db.collection('transactions').document(order_id).update({
                "status": normalized_status,
                "checked_at": firestore.SERVER_TIMESTAMP
            })

            return JsonResponse({
                "order_id": order_id,
                "status": normalized_status,
                "details": details
            })

        except requests.exceptions.Timeout:
            last_error = "Timeout"
        except requests.exceptions.RequestException as e:
            last_error = str(e)

        attempts += 1

    return JsonResponse({
        "order_id": order_id,
        "status": "UNKNOWN",
        "error": last_error
    }, status=200)