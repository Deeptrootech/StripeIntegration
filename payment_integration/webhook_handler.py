import stripe
from datetime import datetime
from user.models import User
from .models import PaymentRecord, StripeCheckoutSession, UserSubscription, SubscriptionStatusChoices, \
    CheckoutSessionStatusChoices, PaymentRecordChoices, Price, Product


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
    print("Subscription created for:", checkoutsession.user.email)


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
    # -----------------------------------------------
    # Skip if subscription already exists
    if UserSubscription.objects.filter(stripe_subscription_id=stripe_subscription_id).exists():
        print("Subscription already exists. Skipping creation.")
        return  # Avoid duplicate creation

    # get user object
    user = User.objects.get(stripe_customer_id=stripe_customer_id)
    # (1) Get completed checkoutsession.( # get checkout session id here)
    checkoutsession = StripeCheckoutSession.objects.filter(stripe_customer_id=stripe_customer_id,
                                                           is_completed=True).order_by("created_at").last()

    # 2) save records in UserSubscription Model
    # here Product and price that no need to create (handle separate webhook for peoduct/price created)
    if stripe_subscription_id:
        try:
            subscription = stripe.Subscription.retrieve(stripe_subscription_id)
        except stripe.error.StripeError as e:
            print(f"Failed to retrieve subscription: {e}")
            return
        # create Product object.
        plan_dict = subscription.get("plan")
        plan_product_id = plan_dict.get("product")
        plan_product_dict = stripe.Product.retrieve(plan_product_id)

        product, _ = Product.objects.get_or_create(stripe_product_id=plan_product_id,
                                                   defaults={"name": plan_product_dict.get("name"),
                                                             "description": plan_product_dict.get("description")}
                                                   )
        # create Price object.
        stripe_plan_id = plan_dict.get("id")  # From Now In Stripe, Plan is handled by price.
        plan_price_dict = stripe.Price.retrieve(stripe_plan_id)
        price, _ = Price.objects.get_or_create(stripe_price_id=stripe_plan_id,
                                               defaults={
                                                   "product": product,
                                                   "amount": plan_price_dict.get("unit_amount"),
                                                   "currency": plan_price_dict.get("currency"),
                                                   "interval": plan_price_dict.get("recurring").get("interval"),
                                                   "interval_count": plan_price_dict.get("recurring").get(
                                                       "interval_count")
                                               }
                                               )
        subscription_start = subscription.get("start_date")
        subscription_end = subscription.get("start_date")  # TODO: THEY are not sending end_date in subscription
        user_subscription, created = UserSubscription.objects.get_or_create(
            stripe_subscription_id=stripe_subscription_id,
            stripe_customer_id=stripe_customer_id,
            defaults={
                "user": user,
                "checkout_session": checkoutsession,
                "price": price,  # if you're tracking this way
                "start_date": datetime.fromtimestamp(subscription_start),
                "end_date": datetime.fromtimestamp(subscription_end),
                "status": SubscriptionStatusChoices.ACTIVE
            }
        )

        print("***************************handle_invoice_paid*************************************")

        # 4) save records in PaymentRecord Model
        PaymentRecord.objects.create(
            user=user_subscription.user,
            amount=amount_paid,
            checkout_session=user_subscription.checkout_session,
            stripe_payment_intent_id=stripe_payment_intent_id,
            status=PaymentRecordChoices.SUCCEEDED,
            invoice_url=invoice_url
        )


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
