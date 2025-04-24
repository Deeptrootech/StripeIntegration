# views.py
import stripe
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
import json

stripe.api_key = settings.STRIPE_SECRET_KEY


class CreateStripeCheckoutSession(APIView):
    """
    Modes in Stripe Checkout:
        Mode	                       Use When You Want To...
    'payment'	                    Collect a one-time payment
    'subscription'	                Start a recurring subscription
    'setup'	                        Collect card details now, charge later (no money taken)

    Here, I have used for subscription Mode checkout.
    Request:
        {
          "email": "user@example.com",
          "plan": "pro"  // or "basic", etc. (We will be using multiple plans)
        }
    """

    def post(self, request):
        try:
            # Example: passed in from frontend
            customer_email = request.data.get("email")
            plan = request.data.get("plan")

            price_map = {
                "basic": "price_ABC",  # This is Price Key(plan key from stripe dashboard)
                "pro": "price_DEF",
            }

            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                mode='subscription',
                subscription_data={
                    "items": [{
                        "price": price_map.get(plan, "price_DEF"),  # Stripe Price ID (linked to product & amount)
                        "quantity": 1  # how many units of that plan/product
                    }]
                },
                customer_email=customer_email,
                success_url='https://yourdomain.com/success?session_id={CHECKOUT_SESSION_ID}',
                cancel_url='https://yourdomain.com/cancel',
            )
            return Response({"url": session.url})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        print("Subscription created for:", session.get("customer_email"))
        # Save user/subscription info here

    return HttpResponse(status=200)


# subscription = stripe.Subscription.create(
#     customer='cus_123',
#     items=[{'price': 'price_abc'}],
#     collection_method='send_invoice',  # or 'charge_automatically' (i.e auto debase money after due_date)
#     days_until_due=7  # Only if using invoice
# )
