from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


# Create your models here.

class User(AbstractUser):
    email = models.EmailField(_("Email address"), unique=True)
    stripe_customer_id = models.CharField(max_length=255, null=True, blank=True)

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email
