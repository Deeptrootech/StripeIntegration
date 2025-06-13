from django.urls import path
from .views import CreateStripeCheckoutSession, stripe_webhook, EstimateTaxView

urlpatterns = [
    path('create-checkout-session/', CreateStripeCheckoutSession.as_view(), name='create-checkout-session'),
    path('webhook/', stripe_webhook, name='stripe-webhook'),
    path('estimate-tax/', EstimateTaxView.as_view(), name='estimate-tax'),
]
