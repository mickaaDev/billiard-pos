from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from datetime import timedelta

class Resource(models.Model):
    RESOURCE_TYPE = (
        ('billiard', 'Бильярд'),
        ('sony', 'Sony'),
        ('bar', 'Бар'),
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
        ('BAR', 'Счет для бара(без вермени)'),
    ]
    is_paused = models.BooleanField(default=False)
    resource = models.ForeignKey(
        Resource, 
        on_delete=models.CASCADE, 
        related_name='sessions',
        verbose_name=_("Стол"),
        null=True, 
        blank=True 
    )
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
        res_name = self.resource.name if self.resource else "БАР"
        mode_display = self.get_mode_display()
        return f"{res_name} [{mode_display}] - ID: {self.pk}"
    
    def get_billable_minutes(self):
        now = self.end_time if self.end_time else timezone.now()
        total_mins = (now - self.start_time).total_seconds() / 60
        
        pause_discount = 0
        for pause in self.pauses.filter(resumed_at__isnull=False):
            # Applying your 10-minute max constraint
            pause_discount += min(pause.duration_minutes, 10)
            
        # If currently paused, calculate current discount too
        active_pause = self.pauses.filter(resumed_at__isnull=True).first()
        if active_pause:
            current_pause_dur = (timezone.now() - active_pause.paused_at).total_seconds() / 60
            pause_discount += min(current_pause_dur, 10)
            
        return max(0, total_mins - pause_discount)
    
    
    def get_total_played_seconds(self):
        # 1. Total time since the very beginning
        end = self.end_time if self.end_time else timezone.now()
        total_elapsed_seconds = (end - self.start_time).total_seconds()
        
        # 2. Subtract pause "discounts" (max 10 mins per pause)
        pause_discount_seconds = 0
        
        # Finished pauses
        for pause in self.pauses.filter(resumed_at__isnull=False):
            # min(actual_pause, 10 minutes)
            discount_mins = min(pause.duration_minutes, 10)
            pause_discount_seconds += (discount_mins * 60)
            
        # Active pause (if the button was just clicked)
        active_pause = self.pauses.filter(resumed_at__isnull=True).first()
        if active_pause:
            current_pause_dur = (timezone.now() - active_pause.paused_at).total_seconds() / 60
            discount_mins = min(current_pause_dur, 10)
            pause_discount_seconds += (discount_mins * 60)
            
        return max(0, total_elapsed_seconds - pause_discount_seconds)
    

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
    def save(self, *args, **kwargs):
        if not self.pk:  # Only runs when the item is first created
            # 1. Snapshot the price to protect against future price changes
            if not self.price_at_order:
                self.price_at_order = self.product.price
            
            # 2. Subtract from Product stock
            if self.product.stock is not None:
                self.product.stock -= self.quantity
                self.product.save()
        
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # 3. Return items to stock if the order is cancelled/deleted
        if self.product.stock is not None:
            self.product.stock += self.quantity
            self.product.save()
        
        super().delete(*args, **kwargs)

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
        return f"Смена {self.user.username} ({self.start_time.strftime('%d.%m %H:%M')})"

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
    
    def get_shift_stock_summary(self):
        """
        Returns how many items were sold vs how many were added during this shift.
        """
        # Items sold during this shift
        sales = SessionItem.objects.filter(session__shift=self).values(
            'product__name'
        ).annotate(total_sold=Sum('quantity'))

        # Stock movements (deliveries/corrections) during this shift
        movements = StockMovement.objects.filter(shift=self).values(
            'product__name', 'type'
        ).annotate(total_change=Sum('quantity'))

        return {
            'sales': sales,
            'movements': movements
        }

    class Meta:
        verbose_name = 'Смена'
        verbose_name_plural = 'Смены'


class StockMovement(models.Model):
    MOVEMENT_TYPE = (
        ('addition', 'Приход (Доставка)'),
        ('correction', 'Коррекция (Инвентаризация)'),
        ('waste', 'Списание (Брак/Разлив)'),
    )

    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='movements',
        verbose_name=_("Товар")
    )
    shift = models.ForeignKey(
        Shift, 
        on_delete=models.CASCADE, 
        related_name='stock_movements',
        verbose_name=_("Смена")
    )
    quantity = models.IntegerField(verbose_name=_("Количество"))
    type = models.CharField(
        max_length=20, 
        choices=MOVEMENT_TYPE, 
        verbose_name=_("Тип движения")
    )
    comment = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name=_("Комментарий")
    )
    timestamp = models.DateTimeField(
        auto_now_add=True, 
        verbose_name=_("Дата и время")
    )

    def save(self, *args, **kwargs):
        if not self.pk:
            # Ensure quantity is positive for logic consistency
            qty = abs(self.quantity) 
            
            if self.type == 'addition':
                self.product.stock = (self.product.stock or 0) + qty
            elif self.type == 'waste':
                self.product.stock = (self.product.stock or 0) - qty
            elif self.type == 'correction':
                # Overwrites the stock with the actual counted amount
                self.product.stock = self.quantity 
            
            self.product.save()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _("Движение товара")
        verbose_name_plural = _("Движения товаров")
        ordering = ['-timestamp']

class SessionPause(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='pauses')
    paused_at = models.DateTimeField(auto_now_add=True)
    resumed_at = models.DateTimeField(null=True, blank=True)

    @property
    def duration_minutes(self):
        if self.resumed_at:
            diff = self.resumed_at - self.paused_at
            return diff.total_seconds() / 60
        return 0

    class Meta:
        verbose_name = "Пауза сессии"
        verbose_name_plural = "Паузы сессий"