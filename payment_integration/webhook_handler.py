import stripe
from datetime import datetime
from user.models import User
from .models import (PaymentRecord, StripeCheckoutSession, UserSubscription, SubscriptionStatusChoices,
                     CheckoutSessionStatusChoices, PaymentRecordChoices, Price, Product)
from .utils import get_or_create_product, get_or_create_price, create_user_subscription, create_payment_record


def handle_checkout_session_expired(event):
    """
    set checkout session status=expired.
    """
    print("***************************handle_checkout_session_expired**********************************")
    session = event['data']['object']
    stripe_checkout_session_id = session.get('id')
    stripe_customer_id = session.get('customer')

    # 2) retrieve StripeCheckoutSession object and set status = Expired
    checkoutsession = StripeCheckoutSession.objects.get(stripe_customer_id=stripe_customer_id,
                                                        stripe_checkout_session_id=stripe_checkout_session_id,
                                                        status=CheckoutSessionStatusChoices.CREATED,
                                                        )
    checkoutsession.status = CheckoutSessionStatusChoices.EXPIRED
    checkoutsession.save()


def handle_checkout_session_completed(event):
    """
    Triggered: Immediately after the user completes the Stripe Checkout page.
    TODO- NOTE: This does not mean the invoice is fully paid for recurring subscriptions.
          It only confirms that the checkout session completed successfully.
    - The subscription & invoice objects has already been created in stripe dashboard
    - The session contains:
        session.invoice: the invoice ID
        session.subscription: the subscription ID
    but payment might still be processing at this point
    """
    print("***************************handle_checkout_session_completed**********************************")
    session = event['data']['object']
    stripe_checkout_session_id = session.get('id')
    stripe_customer_id = session.get('customer')
    stripe_subscription_id = session.get('subscription')

    # 1) retrieve StripeCheckoutSession object and set is_completed=True
    checkoutsession = StripeCheckoutSession.objects.get(stripe_customer_id=stripe_customer_id,
                                                        stripe_checkout_session_id=stripe_checkout_session_id,
                                                        status=CheckoutSessionStatusChoices.CREATED,
                                                        )
    checkoutsession.is_completed = True
    checkoutsession.status = CheckoutSessionStatusChoices.COMPLETED
    checkoutsession.save()
    print("CheckoutSession created for:", checkoutsession.user.email)


def handle_invoice_paid(event):
    """
    Triggered: Immediately after the user completes payment for subscription successfully.
    - Now Stripe confirms payment went through
    - The invoice is officially marked as paid
    - Use this to unlock access / activate features
    """
    invoice = event['data']['object']  # Contains the stripe.PaymentIntent
    stripe_payment_intent_id = invoice.get('id')
    amount_paid = invoice.get('amount_paid')
    invoice_url = invoice.get('hosted_invoice_url')
    stripe_subscription_id = invoice.get("parent").get("subscription_details").get("subscription")
    stripe_customer_id = invoice.get('customer')
    # --------------------------------------------------------------------------------------------
    if not stripe_subscription_id:
        print("No subscription found.")
        return
    # Skip if subscription already exists
    if UserSubscription.objects.filter(stripe_subscription_id=stripe_subscription_id).exists():
        print("Subscription already exists. Skipping creation.")
        return

    try:
        user = User.objects.get(stripe_customer_id=stripe_customer_id)
        checkoutsession = StripeCheckoutSession.objects.filter(
            stripe_customer_id=stripe_customer_id,
            is_completed=True
        ).order_by("created_at").last()

        subscription = stripe.Subscription.retrieve(stripe_subscription_id)
        plan = subscription.get("plan")
        product = get_or_create_product(plan.get("product"))
        price = get_or_create_price(plan.get("id"), product)

        user_subscription = create_user_subscription(
            user, stripe_subscription_id, stripe_customer_id, checkoutsession, price, subscription
        )

        create_payment_record(
            user_subscription.user,
            invoice.get("amount_paid"),
            checkoutsession,
            invoice.get("id"),
            invoice.get("hosted_invoice_url")
        )

        print("✅ Subscription and payment record created successfully.")

    except User.DoesNotExist:
        print(f"❌ User with customer_id {stripe_customer_id} not found.")
    except stripe.error.StripeError as e:
        print(f"❌ Stripe API error: {str(e)}")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")


def handle_payment_intent_failed(event):
    payment_intent = event['data']['object']
    PaymentRecord.objects.create(
        payment_intent_id=payment_intent['id'],
        amount=payment_intent['amount_received'],
        status='failed'
    )


def handle_invoice_payment_succeeded(event):
    invoice = event['data']['object']
    # Add your logic to process invoice payment success here


def handle_invoice_payment_failed(event):
    invoice = event['data']['object']
    # Add your logic to handle failed invoice payment here


def handle_other_events(event):
    # Handle other events if needed
    print(f"Unhandled event type: {event['type']}")
