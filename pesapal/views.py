import os
import uuid
import json
import requests
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import JsonResponse
from .utils import update_booking_status, query_zenopay_payment_status

# 🔐 Load API key from Render environment
ZENOPAY_API_KEY = os.environ.get("ZENOPAY_API_KEY")
WEBHOOK_SECRET = ZENOPAY_API_KEY  # Same key used to verify webhook

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

        order_id = str(uuid.uuid4())  # Unique transaction ID

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
            "webhook_url": "https://smartconnect-pesapal-api.onrender.com/zenopay/webhook"
        }

        print("🔑 ZENOPAY_API_KEY:", ZENOPAY_API_KEY)
        print("📦 Sending to Zenopay:", json.dumps(payload, indent=2))

        res = requests.post("https://zenoapi.com/api/payments/mobile_money_tanzania", headers=headers, json=payload)
        res.raise_for_status()
        response_data = res.json()

        print("📥 Zenopay response:", response_data)

        return Response({
            "status": "initiated",
            "order_id": order_id,
            "zenopay_response": response_data
        })

    except Exception as e:
        print(f"❌ Initiation error: {e}")
        return Response({"error": str(e)}, status=500)


# 📡 Step 2: Webhook Handler
@api_view(['POST'])
def zenopay_webhook(request):
    try:
        print("📨 Webhook received:", request.data)

        # Verify x-api-key header
        incoming_key = request.headers.get("x-api-key")
        if incoming_key != WEBHOOK_SECRET:
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
        print(f"❌ Webhook error: {e}")
        return Response({"error": "Internal server error"}, status=500)


# ✅ Step 3: Manual Status Check (with normalization)
@api_view(['GET'])
def check_zenopay_status(request, order_id):
    try:
        headers = {
            "x-api-key": ZENOPAY_API_KEY
        }

        url = f"https://zenoapi.com/api/payments/order-status?order_id={order_id}"
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        status_data = res.json()

        print("📊 Status check response:", status_data)

        # Normalize Zenopay status
        raw_status = status_data.get("result")
        normalized_status = "COMPLETED" if raw_status == "SUCCESS" else raw_status

        return JsonResponse({
            "order_id": order_id,
            "status": normalized_status,
            "details": status_data.get("data", [])
        })

    except Exception as e:
        print(f"❌ Status check error: {e}")
        return JsonResponse({"error": str(e)}, status=500)