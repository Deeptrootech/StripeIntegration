# views.py
import stripe
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from datetime import datetime

from payment_integration.models import StripeCheckoutSession, CheckoutSessionStatusChoices
from payment_integration.tax_estimation.tax_estimation import order_tax_estimation_calculation_payload
from user.models import User
from payment_integration.webhook_handler import handle_invoice_paid, handle_payment_intent_failed, \
    handle_invoice_payment_succeeded, handle_invoice_payment_failed, handle_other_events, \
    handle_checkout_session_completed, handle_checkout_session_expired

stripe.api_key = settings.STRIPE_SECRET_KEY


class CreateStripeCheckoutSession(APIView):
    """
    JUST REFER "STRIPE PAYMENT" DOC.
    YOU WILL GET WHY THIS CLASS CREATED AND HOW TO USE WEBHOOK(below "stripe_webhook" func)

    Modes in Stripe Checkout:
        Mode	                       Use When You Want To...
    'payment'	                    Collect a one-time payment
    'subscription'	                Start a recurring subscription
    'setup'	                        Collect card details now, charge later (no money taken)

    Here, I have used for subscription Mode checkout.
    Request:
        {
          "plan": "pro"  // or "basic", etc. (We will be using multiple plans)
        }

    Response:
    Step 1: creates checkout session entry to stripe dashboard and send Payment URL
    Step 2: after click that URL and paying successfully It will be rediredted to given success_url.
    """

    def get_or_create_stripe_customer(self):
        user = self.request.user
        if not user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=user.email,
                metadata={"user_id": user.id}
            )
            user.stripe_customer_id = customer.id
            user.save()
        else:
            customer = stripe.Customer.retrieve(user.stripe_customer_id)
        return customer

    def checkout_session_created(self, session):
        print("***************************checkout_session_created**********************************")
        stripe_checkout_session_id = session.get('id')
        stripe_customer_id = session.get('customer')
        checkout_session_expire_at = session.get('expires_at')
        checkout_session_created_at = session.get('created')
        stripe_customer_email = session.get('customer_details').get("email")

        # 1) get DB user bases on stripe user email and update with stripe_customer_id
        user = User.objects.get(email=stripe_customer_email)
        user.stripe_customer_id = stripe_customer_id
        user.save()

        # 2) create Checkout Session (SESSION JUST CREATED, NOT COMPLETED YET.)
        session_expire_at = datetime.fromtimestamp(checkout_session_expire_at)
        session_created_at = datetime.fromtimestamp(checkout_session_created_at)
        StripeCheckoutSession.objects.create(user=user,
                                             stripe_customer_id=stripe_customer_id,
                                             stripe_checkout_session_id=stripe_checkout_session_id,
                                             is_completed=False,
                                             status=CheckoutSessionStatusChoices.CREATED,
                                             session_created_at=session_created_at,
                                             session_expire_at=session_expire_at)

    def post(self, request):
        """
        You do not need to call stripe.Subscription.create manually,
        when using Checkout with mode='subscription'.
        Stripe creates the subscription automatically once Checkout is initiated.
        """
        try:
            # Example: passed in from frontend
            plan = request.data.get("plan")

            price_map = {
                "basic": "price_ABC",
                "pro": "price_1RGeD6IGCuzeTufHrLmC4gs5",  # This is Price Key(plan key from stripe dashboard)
            }

            session = stripe.checkout.Session.create(
                customer=self.get_or_create_stripe_customer().id,
                payment_method_types=['card'],
                mode='subscription',
                line_items=[{
                    "price": price_map.get(plan, "price_1RGeD6IGCuzeTufHrLmC4gs5"),
                    # Stripe Price ID (linked to product & amount)
                    "quantity": 1  # how many units of that plan/product
                }],
                success_url='https://www.google.com/',
                cancel_url='https://yourdomain.com/cancel',
            )
            self.checkout_session_created(session)
            return Response({"url": session.url})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class EstimateTaxView(APIView):
    def get_client_ip(self, request):
        # TODO: add IPWare
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0]
        return request.META.get("REMOTE_ADDR")

    def get(self, request):
        """
        # Create a tax calculation using Stripbe Tax API
        --- IMP: Stripe combines product.tax_code + customer.address to apply the correct local tax rate.
        """
        calculation_payload = order_tax_estimation_calculation_payload(self.get_client_ip(request))
        calc = stripe.tax.Calculation.create(**calculation_payload)
        if not calc:
            return Response(["Tax calculation failed"])
        return Response({
            "plan_price": calc["tax_breakdown"][0]["taxable_amount"] / 100,
            "sales_tax": calc["tax_breakdown"][0]["amount"] / 100,
            "total_payable_amount": calc["amount_total"] / 100,
            "sales_tax_rate": calc["tax_breakdown"][0]["tax_rate_details"]["percentage_decimal"]
        })


@csrf_exempt
def stripe_webhook(request):
    """
    INTEGRATION OF STRIPE WEBHOOK IN OUR APPLICATION:
    - you know when each webhook called. (ref. prepared doc)
    - create function (here, this function) to handle webhook call.
    1) After creating this function... go to stripe dashboard clicking below link.
       https://dashboard.stripe.com/test/workbench/webhooks
    2) Click "Add destination"
    3) Select events: select webhook event which you want to listen to.
       e.g., checkout.session.completed, invoice.payment_succeeded, etc.
    4) Choose destination type & Configure your destination: enter the URL of your webhook endpoint,
       e.g., https://yourdomain.com/webhook/. (URL should be publically accessible)
       IMP: (For Publically accessible URL) For Local... Use Ngrok - (You can always Edit Destination)
    5) add different webhook event handler to handle each webhook call from stripe as given below.
    """
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET  # Signing secret (i.e. "whsec_X...")

    # ---------- Just for Debuggging ------------
    # Stripe includes a timestamp in the signature,
    # so you may get a mismatch if your server's time is out of sync with Stripe’s time.
    # That might cause error so, just checking that below.
    # 1) Extract timestamp from the signature header
    timestamp = int(sig_header.split(',')[0].split('=')[1])
    import time
    # 2) Log the timestamp and current server time for debugging
    print(f"Stripe timestamp: {timestamp}")
    print(f"Current server time: {int(time.time())}")
    # --------------------------------------------

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
        # Handle the event using appropriate handler (Handlers are for mode = 'subscription')
        if event['type'] == 'checkout.session.expired':
            handle_checkout_session_expired(event)
        elif event['type'] == 'checkout.session.completed':
            handle_checkout_session_completed(event)
        elif event['type'] == 'invoice.paid':
            handle_invoice_paid(event)
        elif event['type'] == 'payment_intent.payment_failed':
            handle_payment_intent_failed(event)
        elif event['type'] == 'invoice.payment_succeeded':
            handle_invoice_payment_succeeded(event)
        elif event['type'] == 'invoice.payment_failed':
            handle_invoice_payment_failed(event)
        else:
            handle_other_events(event)

        # Return a response to acknowledge receipt of the event
        return JsonResponse({'status': 'success'}, status=200)

    except ValueError as e:
        print(f"Invalid payload: {e}")
        return JsonResponse({'status': 'failure'}, status=400)
    except stripe.error.SignatureVerificationError as e:
        print(f"Invalid signature: {e}")
        return JsonResponse({'status': 'failure'}, status=400)
        # return HttpResponse(status=400)
