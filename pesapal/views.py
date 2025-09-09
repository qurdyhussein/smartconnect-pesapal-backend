import os
import requests
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