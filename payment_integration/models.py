from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Product(models.Model):
    """
    What you're selling — e.g., "Pro Plan", "Monthly Subscription"

    To create Product in stripe:
    stripe.Product.create(name="AI Pro Plan")
    """
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=500, null=True, blank=True)
    stripe_product_id = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class PriceBillingCycleChoices:
    MONTHLY = 'monthly'
    YEARLY = 'yearly'

    BILLING_CYCLE_CHOICES = (
        (MONTHLY, 'Monthly'),
        (YEARLY, 'Yearly'),
    )


class Price(models.Model):
    """
    TODO (IMP): Plan Model is Deprecated, now It handled by Price object itself.
    Price replace old Plan model

    To create Price in stripe:
    stripe.Price.create(
        unit_amount=1000,  # $10.00
        currency="usd",
        recurring={"interval": "month"},
        product=product_id,
    )
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='prices')
    stripe_price_id = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Per product unit amount")
    currency = models.CharField(max_length=10)
    interval = models.CharField(max_length=20, choices=PriceBillingCycleChoices.BILLING_CYCLE_CHOICES,
                                default=PriceBillingCycleChoices.MONTHLY)  # e.g., 'month', 'year'
    interval_count = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.amount} {self.currency} / {self.interval}"


class CheckoutSessionStatusChoices:
    CREATED = 'created'
    EXPIRED = 'expired'
    COMPLETED = 'completed'

    STATUS_CHOICES = (
        (CREATED, "Created"),
        (EXPIRED, "Expired"),
        (COMPLETED, "Completed"),
    )


class StripeCheckoutSession(models.Model):
    """
    Stores details regarding Stripe checkout attempts. (Detail of user's every checkout attempts)
    """
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_checkout_sessions')
    stripe_customer_id = models.CharField(max_length=255)
    stripe_checkout_session_id = models.CharField(max_length=255, unique=True)
    price = models.ForeignKey(Price, on_delete=models.CASCADE, related_name='price_checkout_sessions', null=True,
                              blank=True)
    is_completed = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=CheckoutSessionStatusChoices.STATUS_CHOICES, null=True, blank=True)
    session_created_at = models.DateTimeField(null=True, blank=True)
    session_expire_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.email if self.user else 'Guest'} - {self.stripe_checkout_session_id}"


class PaymentRecordChoices:
    ONE_TIME = 'one_time'
    SUBSCRIPTION = 'subscription'
    CARD = 'card'
    PENDING = 'pending'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'

    PAYMENT_TYPE_CHOICES = (
        (ONE_TIME, 'One-Time'),
        (SUBSCRIPTION, 'Subscription'),
    )

    PAYMENT_MODE_CHOICES = (
        (CARD, 'Card'),
    )

    PAYMENT_STATUS = (
        (PENDING, 'Pending'),
        (SUCCEEDED, 'Succeeded'),
        (FAILED, 'Failed'),
    )


class PaymentRecord(models.Model):
    """
    Stores details regarding payment attempts (first_time or recurring).
    (Detail of user's every payment attempts while checking out)
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_payment_records')
    payment_type = models.CharField(max_length=20, choices=PaymentRecordChoices.PAYMENT_TYPE_CHOICES,
                                    default=PaymentRecordChoices.SUBSCRIPTION)
    payment_mode = models.CharField(max_length=20, choices=PaymentRecordChoices.PAYMENT_MODE_CHOICES,
                                    default=PaymentRecordChoices.CARD)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    invoice_url = models.CharField(null=True, blank=True)
    checkout_session = models.ForeignKey(
        StripeCheckoutSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checkout_payment_records'
    )
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True,
                                                help_text="Stripe's internal ID for a specific payment attempt")
    status = models.CharField(max_length=20, choices=PaymentRecordChoices.PAYMENT_STATUS,
                              default=PaymentRecordChoices.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - ₹{self.amount} - {self.status}"


class SubscriptionStatusChoices:
    ACTIVE = 'active'
    INACTIVE = 'inactive'

    STATUS_CHOICES = (
        (ACTIVE, "Active"),
        (INACTIVE, "Inactive"),
    )


class UserSubscription(models.Model):
    """
    1. Only one UserSubscription entry allowed In entire website. (not able to create other any)
    - Use OneToOneField for "user"
    - Use unique=True for "stripe_customer_id"
    - Use unique=True for "stripe_subscription_id"

    2. Multiple UserSubscription entries allowed.
    (i) If Your user can only subscribe to one plan at a time (upgrade/downgrade allowed).
    - Use ForeignKey for "user"
    - stripe_subscription_item_id (In one suscription, one product/item subscribed)
      (No need to create another model for "subscription_item"
      just add id of suscribed item as stripe_subscription_item_id In current(UserSubscription) model.)
    (ii) If You offer add-ons, or parallel subscriptions (like Netflix + Extra Screens + Kids mode, etc.)
    - Use ForeignKey for "user"
    - stripe_subscription_item_id (In one parent suscription, many products/items subscribed)
    then...
    create another model like through between... UserSubscription & Price
    having fields
    stripe_subscription_item_id, price(obj)
    and remove those fields from  UserSubscription and add through model m2m instead.


    Here, below Model & create_user_subscription() created for 2-(i).
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_subscriptions',
                             help_text="a user can have multiple subscription, But only one at a time")
    stripe_subscription_id = models.CharField(max_length=100, null=True, blank=True)
    stripe_subscription_item_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=100)
    price = models.ForeignKey(Price, on_delete=models.CASCADE, related_name='price_subscriptions', null=True,
                              blank=True)
    checkout_session = models.ForeignKey(
        StripeCheckoutSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checkout_ubscriptions'
    )
    status = models.CharField(max_length=20, choices=SubscriptionStatusChoices.STATUS_CHOICES,
                              default=SubscriptionStatusChoices.INACTIVE)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.price} - {self.status}"
