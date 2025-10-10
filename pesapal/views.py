import os
import uuid
import json
import requests
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import JsonResponse
from .utils import update_booking_status, query_zenopay_payment_status
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

ZENOPAY_API_KEY = os.environ.get("ZENOPAY_API_KEY")
WEBHOOK_SECRET = os.environ.get("ZENOPAY_WEBHOOK_SECRET", ZENOPAY_API_KEY)

# ✅ Step 1: Initiate Payment
@api_view(['POST'])
def initiate_zenopay_payment(request):
    try:
        data = request.data
        phone = data.get("phone")
        amount = data.get("amount")
        buyer_name = data.get("buyer_name", "SmartConnect User")
        buyer_email = data.get("buyer_email", "user@smartconnect.tz")
        customer_id = data.get("customer_id", "unknown")
        package = data.get("package")
        network = data.get("network")
        channel = data.get("channel") or network
        payment_method = data.get("payment_method", "unspecified")

        if not phone or not amount:
            return Response({"error": "Missing phone or amount"}, status=400)

        try:
            amount = int(amount)
        except (ValueError, TypeError):
            return Response({"error": "Invalid amount"}, status=400)

        order_id = str(uuid.uuid4())

        db.collection('transactions').document(order_id).set({
            "order_id": order_id,
            "phone": phone,
            "amount": amount,
            "buyer_name": buyer_name,
            "buyer_email": buyer_email,
            "customer_id": customer_id,
            "package": package,
            "network": network,
            "channel": channel,
            "payment_method": payment_method,
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
            "channel": channel,
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

# ✅ Step 2: Webhook Handler
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

        print("📦 Webhook payload:", data)

        order_id = data.get("order_id")
        status = data.get("payment_status_description") or data.get("payment_status")
        method = data.get("payment_method") or "unspecified"
        code = data.get("confirmation_code") or data.get("reference") or "N/A"
        channel = data.get("channel") or "unknown"
        transid = data.get("transid") or data.get("transaction_id") or "pending"

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

        # ✅ Fallback: If channel or transid are missing, trigger manual check
        if channel == "unknown" or transid == "pending":
            fallback = query_zenopay_payment_status(order_id)
            transaction_ref.update({
                "channel": fallback.get("channel", channel),
                "transid": fallback.get("transid", transid),
                "confirmation_code": fallback.get("confirmation_code", code),
                "payment_method": fallback.get("payment_method", method),
                "checked_at": firestore.SERVER_TIMESTAMP
            })

        if status.upper() == "COMPLETED":
            transaction_doc = transaction_ref.get()
            transaction_data = transaction_doc.to_dict()
            customer_id = transaction_data.get("customer_id")
            package = transaction_data.get("package")
            network = transaction_data.get("network")

            voucher_query = db.collection('vouchers')\
                .where('status', '==', 'available')\
                .where('package', '==', package)\
                .where('network', '==', network)\
                .limit(1)\
                .stream()

            voucher_doc = next(voucher_query, None)

            if voucher_doc:
                voucher_id = voucher_doc.id
                voucher_data = voucher_doc.to_dict()
                voucher_code = voucher_data.get("code") or voucher_id

                db.collection('vouchers').document(voucher_id).update({
                    'assigned_to': customer_id,
                    'status': 'assigned',
                    'assigned_at': firestore.SERVER_TIMESTAMP
                })

                transaction_ref.update({
                    'assigned_voucher': voucher_code,
                    'assigned_at': firestore.SERVER_TIMESTAMP
                })

                print(f"🎁 Voucher {voucher_code} assigned to {customer_id}")
            else:
                print(f"⚠️ No available voucher for package={package}, network={network}")

        print(f"✅ Webhook processed for order {order_id} - {status}")
        return Response({"status": "received", "order_id": order_id})

    except Exception as e:
        print("🔥 Webhook error:", str(e))
        return Response({"error": "Internal server error"}, status=500)

# ✅ Step 3: Manual Status Check
@api_view(['GET'])
def check_zenopay_status(request, order_id):
    result = query_zenopay_payment_status(order_id)
    return JsonResponse(result)