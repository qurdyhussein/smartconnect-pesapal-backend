import os
import uuid
import json
import requests
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import JsonResponse
from .utils import update_booking_status

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

        order_id = str(uuid.uuid4())

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

        res.raise_for_status()
        response_data = res.json()

        return Response({
            "status": "initiated",
            "order_id": order_id,
            "zenopay_response": response_data
        })

    except Exception as e:
        return Response({"error": str(e)}, status=500)


# 📡 Step 2: Webhook Handler
@csrf_exempt
@api_view(['POST'])
def zenopay_webhook(request):
    try:
        incoming_key = request.headers.get("x-api-key")
        print("🔐 Incoming x-api-key:", incoming_key)

        if incoming_key != WEBHOOK_SECRET:
            print("❌ Webhook rejected: invalid x-api-key")
            return Response({"error": "Unauthorized webhook"}, status=403)

        order_id = request.data.get("order_id")
        status = request.data.get("payment_status_description")
        method = request.data.get("payment_method")
        code = request.data.get("confirmation_code")
        channel = request.data.get("channel")
        transid = request.data.get("transid")

        if not order_id or not status:
            return Response({"error": "Missing order_id or payment_status"}, status=400)

        update_booking_status(order_id, {
            "payment_status_description": status,
            "payment_method": method,
            "confirmation_code": code,
            "channel": channel,
            "transid": transid
        })

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
            res.raise_for_status()
            status_data = res.json()

            raw_status = status_data.get("result")
            details = status_data.get("data", [])
            payment_status = details[0].get("payment_status") if details else None

            if raw_status == "SUCCESS" and payment_status == "COMPLETED":
                normalized_status = "COMPLETED"
            elif payment_status == "PENDING":
                normalized_status = "PENDING"
            else:
                normalized_status = "FAIL"

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