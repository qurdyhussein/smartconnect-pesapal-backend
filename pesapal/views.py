import os
import time
import requests
import json
from dotenv import load_dotenv
from rest_framework.decorators import api_view
from rest_framework.response import Response

load_dotenv()

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


@api_view(['POST'])
def submit_order_request(request):
    try:
        data = request.data
        phone = data.get("phone")
        amount = data.get("amount")
        email = data.get("email", "user@example.com")
        first_name = data.get("first_name", "Smart")
        last_name = data.get("last_name", "Connect")

        # Step 1: Get token
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

        # Step 2: Submit order
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        order_id = f"SC{int(time.time() * 1000)}"
        notification_id = os.getenv("PESAPAL_NOTIFICATION_ID")  # Must be set in .env

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