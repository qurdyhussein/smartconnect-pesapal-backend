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

        merchant_reference = f"SC{int(time.time() * 1000)}"

        body = {
            "amount": str(amount),
            "currency": "TZS",
            "description": "SmartConnect Ticket",
            "type": "MERCHANT",
            "reference": f"SC{int(time.time() * 1000)}",
            "phone_number": phone,
            "email": "user@example.com",
            "callback_url": "https://smartconnect-pesapal-api.onrender.com/ipn/"
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