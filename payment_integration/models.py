from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Plan(models.Model):
    """
    stores all subscription plans defined in stripe dashboard.
    """
    BILLING_CYCLE_CHOICES = (
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    )
    plan_price_id = models.CharField(max_length=100)  # Stripe Price ID
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    billing_cycle = models.CharField(max_length=20, choices=BILLING_CYCLE_CHOICES)

    def __str__(self):
        return f"{self.name} - {self.billing_cycle} - ₹{self.price}"


class StripeCheckoutSession(models.Model):
    """
    Stores details regarding Stripe checkout attempts. (Detail of user's every checkout attempts)
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_checkout_sessions')
    stripe_customer_id = models.CharField(max_length=255, unique=True)
    stripe_checkout_session_id = models.CharField(max_length=255, unique=True)
    plan = models.ForeignKey(User, on_delete=models.CASCADE, related_name='plan_checkout_sessions')
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email if self.user else 'Guest'} - {self.stripe_checkout_session_id}"


class PaymentRecord(models.Model):
    """
    Stores details regarding payment attempts (first_time or recurring).
    (Detail of user's every payment attempts while checking out)
    """
    PAYMENT_TYPE_CHOICES = (
        ('one_time', 'One-Time'),
        ('subscription', 'Subscription'),
    )
    PAYMENT_MODE_CHOICES = (
        ('card', 'Card'),
    )
    PAYMENT_STATUS = (
        ('pending', 'Pending'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_payment_records')
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    checkout_session = models.ForeignKey(
        StripeCheckoutSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checkout_payment_records'
    )
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True,
                                                help_text="Stripe's internal ID for a specific payment attempt")
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - ₹{self.amount} - {self.status}"


class UserSubscription(models.Model):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive"),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_subscriptions')
    stripe_subscription_id = models.CharField(max_length=100, unique=True)
    stripe_customer_id = models.CharField(max_length=100, unique=True)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name='plan_subscriptions')
    checkout_session = models.ForeignKey(
        StripeCheckoutSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checkout_ubscriptions'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.plan.name} - {self.status}"
