from django.db import models
from django.contrib.auth.models import User


class Resource(models.Model):
    RESOURCE_TYPE = (
        ('billiard', 'Бильярд'),
        ('sony', 'Sony'),
    )

    name = models.CharField(max_length=50)
    type = models.CharField(max_length=20, choices=RESOURCE_TYPE)
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.type})"
    
    def current_session(self):
        return self.sessions.filter(is_active=True).first()


class Product(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.name

class Session(models.Model):
    """
    Tracks a session on a resource
    """
    MODE_CHOICES = [
        ('OPEN', 'Open (Pay at end)'),
        ('PREPAID', 'Pre-paid (Fixed time)'),
    ]

    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='sessions')
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default='OPEN')
    prepaid_minutes = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.resource.name} - {self.pk}"


class ResourceUsage(models.Model):
    session = models.ForeignKey(
        Session,
        related_name='usages',
        on_delete=models.CASCADE  # session deleted → usage deleted
    )
    resource = models.ForeignKey(
        Resource,
        on_delete=models.PROTECT  # do not lose history
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)


class OrderItem(models.Model):
    session = models.ForeignKey(
        Session,
        related_name='orders',
        on_delete=models.CASCADE
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT
    )
    quantity = models.PositiveIntegerField()


class Bill(models.Model):
    session = models.OneToOneField(
        Session,
        on_delete=models.PROTECT
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    closed_at = models.DateTimeField(auto_now_add=True)


class SessionItem(models.Model):
    # Change 'on_parent_delete' to 'on_delete'
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    price_at_order = models.DecimalField(max_digits=10, decimal_places=2)

    def total_price(self):
        # We add a check: if price_at_order is None, use 0.00
        price = self.price_at_order if self.price_at_order is not None else 0
        return self.quantity * price