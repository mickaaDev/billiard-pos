from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _


class Resource(models.Model):
    RESOURCE_TYPE = (
        ('billiard', 'Бильярд'),
        ('sony', 'Sony'),
    )

    name = models.CharField(max_length=50,verbose_name=_("Название"))
    type = models.CharField(max_length=20, choices=RESOURCE_TYPE, verbose_name=_("Вид"))
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Цена за час"))
    is_active = models.BooleanField(default=True, verbose_name=_("Активен"))

    def __str__(self):
        return f"{self.name} ({self.type})"
    
    def current_session(self):
        return self.sessions.filter(is_active=True).first()

    class Meta:
        verbose_name = 'Стол'
        verbose_name_plural = 'Столы'


class Product(models.Model):
    name = models.CharField(max_length=100,verbose_name=_("Название"))
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Цена продажи"))
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_("Цена закупа"))
    stock = models.IntegerField(null=True, blank=True,verbose_name=_("Кол-во товара"))

    def __str__(self):
        return self.name
    
    @property
    def margin(self):
        return self.price - self.cost_price

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'

class Session(models.Model):
    """
    Tracks a session on a resource
    """
    MODE_CHOICES = [
        ('OPEN', 'Открыть (Оплата в конце)'),
        ('PREPAID', 'Предоплата (фиксированное время)'),
    ]

    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='sessions',verbose_name=_("Стол"))
    start_time = models.DateTimeField(auto_now_add=True,verbose_name=_("Начато"))
    end_time = models.DateTimeField(null=True, blank=True,verbose_name=_("Закончено"))
    is_active = models.BooleanField(default=True,verbose_name=_("Активен"))
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,verbose_name=_("Создано"))
    
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default='OPEN',verbose_name=_("Вид"))
    prepaid_minutes = models.PositiveIntegerField(null=True, blank=True,verbose_name=_("Предоплата"))
    shift = models.ForeignKey(
        'Shift', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='sessions',
        verbose_name=_("Смена")
    )

    def __str__(self):
        return f"{self.resource.name} - {self.pk}"
    
    class Meta:
        verbose_name = 'Сессия'
        verbose_name_plural = 'Сессии'


class ResourceUsage(models.Model):
    session = models.ForeignKey(
        Session,
        related_name='usages',
        on_delete=models.CASCADE  # session deleted → usage deleted
        ,verbose_name=_("Сессия")
    )
    resource = models.ForeignKey(
        Resource,
        on_delete=models.PROTECT,  # do not lose history
        verbose_name=_("Стол")
    )
    started_at = models.DateTimeField(verbose_name=_("Начато"))
    ended_at = models.DateTimeField(null=True, blank=True,verbose_name=_("Закончено"))

    class Meta:
        verbose_name = 'Использование товара'
        verbose_name_plural = 'Использование товаров'


class OrderItem(models.Model):
    session = models.ForeignKey(
        Session,
        related_name='orders',
        on_delete=models.CASCADE,verbose_name=_("Сессия")
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,verbose_name=_("Товар")
    )
    quantity = models.PositiveIntegerField(verbose_name=_("Кол-во"))
    class Meta:
        verbose_name = 'Заказ товара'
        verbose_name_plural = 'Заказы товаров'


class Bill(models.Model):
    session = models.OneToOneField(
        Session,
        on_delete=models.PROTECT,verbose_name=_("Сессия")
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2,verbose_name=_("Общая сумма"))
    closed_at = models.DateTimeField(auto_now_add=True,verbose_name=_("Закрыто в"))
    class Meta:
        verbose_name = 'Счет'
        verbose_name_plural = 'Счета'

class SessionItem(models.Model):
    # Change 'on_parent_delete' to 'on_delete'
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='items',verbose_name=_("Сессия"))
    product = models.ForeignKey(Product, on_delete=models.PROTECT,verbose_name=_("Товар"))
    quantity = models.PositiveIntegerField(default=1,verbose_name=_("Кол-во"))
    price_at_order = models.DecimalField(max_digits=10, decimal_places=2,verbose_name=_("Цена при заказе"))

    def total_price(self):
        # We add a check: if price_at_order is None, use 0.00
        price = self.price_at_order if self.price_at_order is not None else 0
        return self.quantity * price

    class Meta:
        verbose_name = 'Товар сессии'
        verbose_name_plural = 'Товары сессии'
        ordering = ['id']

class Shift(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,verbose_name=_("Пользователь"))
    start_time = models.DateTimeField(auto_now_add=True,verbose_name=_("Начало(время)"))
    end_time = models.DateTimeField(null=True, blank=True,verbose_name=_("Конец(время)"))
    start_cash = models.DecimalField(max_digits=10, decimal_places=2, default=0,verbose_name=_("Изначальная сумма"))
    end_cash = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,verbose_name=_("Итоговая сумма"))
    is_active = models.BooleanField(default=True,verbose_name=_("Активен"))

    def total_revenue(self):
        from .models import Bill
        
        end_boundary = self.end_time if self.end_time else timezone.now()
        
        # Change 'created_at__range' to 'closed_at__range'
        revenue = Bill.objects.filter(
            closed_at__range=(self.start_time, end_boundary)
        ).aggregate(Sum('total_amount'))['total_amount__sum']
        
        return revenue or 0


    def __str__(self):
        return f"Смена {self.user.username} ({self.start_time.strftime('%d.%m %H:%i')})"

    def clean(self):
        # Check if another shift is already active
        active_shifts = Shift.objects.filter(is_active=True)
        if self.pk:
            active_shifts = active_shifts.exclude(pk=self.pk)
        
        if self.is_active and active_shifts.exists():
            raise ValidationError("Системная ошибка: Уже есть активная смена. Закройте текущую смену перед открытием новой.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def get_shift_report(self):
        from .models import Bill, SessionItem
        from django.db.models import Sum, F
        from django.utils import timezone

        end = self.end_time if self.end_time else timezone.now()
        bills = Bill.objects.filter(closed_at__range=(self.start_time, end))

        total_revenue = bills.aggregate(Sum('total_amount'))['total_amount__sum'] or 0

        items = SessionItem.objects.filter(session__bill__in=bills)

        bar_revenue = 0
        bar_cost = 0
        total_items_sold = 0

        for item in items:
            bar_revenue += item.total_price()
            # Fallback to 0 if cost_price is None
            c_price = item.product.cost_price or 0
            bar_cost += (c_price * item.quantity)
            total_items_sold += item.quantity

        bar_profit = bar_revenue - bar_cost
        time_revenue = total_revenue - bar_revenue

        return {
            'total_revenue': total_revenue,
            'bar_revenue': bar_revenue,
            'bar_profit': bar_profit,
            'time_revenue': time_revenue,
            'items_count': total_items_sold,
            'bar_cost': bar_cost
        }
    @property
    def discrepancy(self):
        """Calculates if the cash drawer is short or over."""
        if self.end_cash is not None:
            expected = self.start_cash + self.total_revenue()
            return self.end_cash - expected
        return 0
    class Meta:
        verbose_name = 'Смена'
        verbose_name_plural = 'Смены'