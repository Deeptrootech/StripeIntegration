import stripe
from datetime import datetime
from .models import (PaymentRecord, UserSubscription, SubscriptionStatusChoices,
                     PaymentRecordChoices, Price, Product)


def get_or_create_product(plan_product_id):
    product_data = stripe.Product.retrieve(plan_product_id)
    product, _ = Product.objects.get_or_create(
        stripe_product_id=plan_product_id,
        defaults={
            "name": product_data.get("name"),
            "description": product_data.get("description")
        }
    )
    return product


def get_or_create_price(stripe_price_id, product):
    price_data = stripe.Price.retrieve(stripe_price_id)
    price, _ = Price.objects.get_or_create(
        stripe_price_id=stripe_price_id,
        defaults={
            "product": product,
            "amount": price_data.get("unit_amount"),
            "currency": price_data.get("currency"),
            "interval": price_data.get("recurring").get("interval"),
            "interval_count": price_data.get("recurring").get("interval_count")
        }
    )
    return price


def create_user_subscription(user, stripe_subscription_id, stripe_customer_id, checkoutsession, price, subscription):
    # TODO: Need to change This function as 2(i) of 'UserSubscription' Model. (use for loop for adding stripe_subscription_item_id)
    start_timestamp = subscription.get("start_date")
    end_timestamp = subscription.get("current_period_end")
    return UserSubscription.objects.create(
        user=user,
        stripe_subscription_id=stripe_subscription_id,
        stripe_customer_id=stripe_customer_id,
        checkout_session=checkoutsession,
        price=price,
        start_date=datetime.fromtimestamp(start_timestamp),
        end_date=datetime.fromtimestamp(end_timestamp),
        status=SubscriptionStatusChoices.ACTIVE
    )


def create_payment_record(user, amount_paid, checkoutsession, payment_intent_id, invoice_url):
    PaymentRecord.objects.create(
        user=user,
        amount=amount_paid,
        checkout_session=checkoutsession,
        stripe_payment_intent_id=payment_intent_id,
        status=PaymentRecordChoices.SUCCEEDED,
        invoice_url=invoice_url
    )
