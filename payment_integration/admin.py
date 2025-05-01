from django.contrib import admin

from .models import Product, Price, StripeCheckoutSession, PaymentRecord, UserSubscription

# Register your models here.
admin.site.register(Product)
admin.site.register(Price)
admin.site.register(StripeCheckoutSession)
admin.site.register(PaymentRecord)
admin.site.register(UserSubscription)
