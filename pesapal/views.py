import os
import time
import requests
import json
from dotenv import load_dotenv
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import JsonResponse
from .utils import update_booking_status, query_pesapal_payment_status

load_dotenv()

# 🔐 Step 1: Get Pesapal Token
@api_view(['POST'])
def get_token(request):
    url = "https://pay.pesapal.com/v3/api/Auth/RequestToken"
    payload = {
        "consumer_key": os.getenv("PESAPAL_CONSUMER_KEY"),
        "consumer_secret": os.getenv("PESAPAL_CONSUMER_SECRET"),
    }
    headers = {"Content-Type": "application/json"}

    try:
        res = requests.post(url, json=payload, headers=headers)
        res.raise_for_status()
        token = res.json().get("token")
        return Response({"token": token})
    except Exception as e:
        return Response({"error": str(e)}, status=500)


# 🧾 Step 2: Submit Order Request
@api_view(['POST'])
def submit_order_request(request):
    try:
        data = request.data
        phone = data.get("phone")
        amount = data.get("amount")
        email = data.get("email", "user@example.com")
        first_name = data.get("first_name", "Smart")
        last_name = data.get("last_name", "Connect")

        token_res = requests.post(
            "https://pay.pesapal.com/v3/api/Auth/RequestToken",
            headers={"Content-Type": "application/json"},
            json={
                "consumer_key": os.getenv("PESAPAL_CONSUMER_KEY"),
                "consumer_secret": os.getenv("PESAPAL_CONSUMER_SECRET"),
            }
        )
        token_res.raise_for_status()
        token = token_res.json().get("token")

        if not token:
            return Response({"error": "Failed to retrieve token"}, status=500)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        order_id = f"SC{int(time.time() * 1000)}"
        notification_id = os.getenv("PESAPAL_NOTIFICATION_ID")

        if not notification_id:
            return Response({"error": "Missing notification_id"}, status=500)

        body = {
            "id": order_id,
            "currency": "TZS",
            "amount": float(amount),
            "description": "SmartConnect Ticket",
            "callback_url": "https://smartconnect-pesapal-api.onrender.com/ipn/",
            "notification_id": notification_id,
            "billing_address": {
                "email_address": email,
                "phone_number": phone,
                "country_code": "TZ"
            }
        }

        print("📦 Request body to Pesapal:", json.dumps(body, indent=2))

        res = requests.post(
            "https://pay.pesapal.com/v3/api/Transactions/SubmitOrderRequest",
            headers=headers,
            json=body
        )

        print("📥 Raw response from Pesapal:", res.text)

        res.raise_for_status()
        return Response(res.json())

    except requests.exceptions.HTTPError as http_err:
        return Response({"error": f"HTTP error: {str(http_err)}"}, status=500)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


# 📡 Step 3: IPN Handler
@api_view(['POST'])
def pesapal_ipn(request):
    try:
        print("📨 IPN payload received:", request.data)

        tracking_id = request.data.get("order_tracking_id")
        merchant_reference = request.data.get("merchant_reference")

        if not tracking_id or not merchant_reference:
            return Response({"error": "Missing tracking_id or merchant_reference"}, status=400)

        token_res = requests.post(
            "https://pay.pesapal.com/v3/api/Auth/RequestToken",
            headers={"Content-Type": "application/json"},
            json={
                "consumer_key": os.getenv("PESAPAL_CONSUMER_KEY"),
                "consumer_secret": os.getenv("PESAPAL_CONSUMER_SECRET"),
            }
        )
        token_res.raise_for_status()
        token = token_res.json().get("token")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        status_url = (
            f"https://pay.pesapal.com/v3/api/Transactions/GetTransactionStatus"
            f"?order_tracking_id={tracking_id}&merchant_reference={merchant_reference}"
        )

        res = requests.get(status_url, headers=headers)
        res.raise_for_status()
        status_data = res.json()

        print("📥 IPN status response:", status_data)

        # ✅ Update booking status in DB
        update_booking_status(merchant_reference, status_data)

        return Response({"status": "received", "data": status_data})

    except Exception as e:
        return Response({"error": str(e)}, status=500)


# ✅ Step 4: Status Check Endpoint
@api_view(['GET'])
def check_payment_status(request, reference):
    try:
        status = query_pesapal_payment_status(reference)
        return JsonResponse({
            "reference": reference,
            "status": status
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)