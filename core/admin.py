import math
from django.contrib import admin, messages
from .models import Resource, Product, Session, Bill, SessionItem, Shift, StockMovement
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.db.models import Sum, Count, F
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.safestring import mark_safe
from django.utils.formats import date_format
from decimal import Decimal

admin.site.site_header = "Панель управления Billiard POS"
admin.site.site_title = "Billiard POS Админ"
admin.site.index_title = "Добро пожаловать в систему управления"

# 1. Stock Movement Admin
@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    # FIXED: Replaced 'timestamp' with 'get_local_timestamp' to apply the timezone conversion
    list_display = ('get_local_timestamp', 'product', 'type', 'quantity', 'shift')
    list_filter = ('type', 'timestamp', 'product')
    
    def get_local_timestamp(self, obj):
        if obj.timestamp:
            # Explicitly force conversion from database UTC storage to Asia/Bishkek time
            local_time = timezone.localtime(obj.timestamp)
            return date_format(local_time, format="d E Y г. H:i", use_l10n=True)
        return "-"
    get_local_timestamp.short_description = "Дата и время"
    get_local_timestamp.admin_order_field = 'timestamp'

    def get_readonly_fields(self, request, obj=None):
        if obj: 
            return [f.name for f in self.model._meta.fields]
        return self.readonly_fields 

    def has_delete_permission(self, request, obj=None):
        return False

    def user_display(self, obj):
        return obj.shift.user.username if obj.shift else "-"
    user_display.short_description = "Сотрудник"


# Inlines
class SessionItemInline(admin.TabularInline):
    model = SessionItem
    extra = 0
    readonly_fields = ('price_at_order', 'get_total')
    def get_total(self, obj):
        if obj.id:
            return f"{obj.total_price():.2f} сом"
        return "0 сом"
    get_total.short_description = "Итого за товар"

class BillInline(admin.StackedInline):
    model = Bill
    extra = 0
    can_delete = False


# 2. Shift Admin
@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    search_fields = ['user__username', 'start_time']
    list_display = (
        'id', 
        'get_shift_date', 
        'user', 
        'is_active', 
        'start_cash', 
        'end_cash', 
        'get_discrepancy', 
        'get_profit'
    )
    list_display_links = ('id', 'get_shift_date')
    readonly_fields = ('start_time', 'end_time', 'get_full_report')

    def get_shift_date(self, obj):
        if obj.start_time:
            # FIXED: Forces time conversion into Asia/Bishkek before date_format processing
            local_time = timezone.localtime(obj.start_time)
            return date_format(local_time, format="d E Y (H:i)", use_l10n=True)
        return "Неизвестно"
    
    get_shift_date.short_description = "Дата/Время начала"
    get_shift_date.admin_order_field = 'start_time'

    def get_discrepancy(self, obj):
        val = obj.discrepancy
        color = "green" if val >= 0 else "red"
        return format_html('<b style="color: {};">{} сом</b>', color, val)
    get_discrepancy.short_description = "Разница (Касса)"

    def get_profit(self, obj):
        report = obj.get_shift_report()
        return f"{report['bar_profit']} сом"
    get_profit.short_description = "Прибыль (Бар)"

    def get_full_report(self, obj):
        if not obj.start_time:
            return "Нет данных"

        report = obj.get_shift_report()
        end = obj.end_time if obj.end_time else timezone.now()
        
        # 1. Product Logic
        items = SessionItem.objects.filter(
            session__bill__closed_at__range=(obj.start_time, end)
        ).values('product__name').annotate(
            total_qty=Sum('quantity'),
            total_rev=Sum(F('quantity') * F('price_at_order')),
            total_cost=Sum(F('quantity') * F('product__cost_price'))
        )

        product_rows = ""
        for item in items:
            rev = item['total_rev'] or 0
            cost = item['total_cost'] or 0
            profit = rev - cost
            product_rows += f"""
                <tr style='border-bottom: 1px solid #ddd;'>
                    <td style='padding: 12px; color: #000;'><b>{item['product__name']}</b></td>
                    <td style='padding: 12px; color: #000; text-align: center;'>{item['total_qty']} шт.</td>
                    <td style='padding: 12px; color: #000; text-align: right;'>{rev} сом</td>
                    <td style='padding: 12px; color: #27ae60; text-align: right; font-weight: bold;'>+{profit} сом</td>
                </tr>"""

        # 2. Resource Logic
        resource_stats = Bill.objects.filter(
            closed_at__range=(obj.start_time, end)
        ).values('session__resource__name').annotate(
            total_earned=Sum('total_amount')
        )

        resource_rows = ""
        for res in resource_stats:
            resource_rows += f"""
                <tr style='border-bottom: 1px solid #ddd;'>
                    <td style='padding: 12px; color: #000;'><b>{res['session__resource__name']}</b></td>
                    <td style='padding: 12px; color: #000; text-align: right; font-weight: bold;'>{res['total_earned']} сом</td>
                </tr>"""

        # 3. WIDE CONTAINER LOGIC
        html_content = f"""
        <div style='background: #ffffff; color: #000; padding: 30px; border-radius: 12px; border: 1px solid #ccc; width: 95%; max-width: 1200px; margin: 0 auto; line-height: 1.4; font-family: sans-serif;'>
            <h2 style='color: #2c3e50; margin-top: 0; border-bottom: 3px solid #3498db; padding-bottom: 15px; font-size: 24px;'>📊 Детальная аналитика смены</h2>
            
            <div style='display:flex; gap: 30px; margin-bottom: 40px;'>
                <div style='background: #f8fbff; padding: 25px; border-radius: 10px; flex: 1; border: 1px solid #bce0ff; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);'>
                    <b style='color: #0056b3; font-size: 18px;'>💰 ВЫРУЧКА</b><br><br>
                    <div style='font-size: 16px;'>
                        Бар: <span style='float: right;'>{report['bar_revenue']} сом</span><br>
                        Время: <span style='float: right;'>{report['time_revenue']} сом</span><br>
                        <hr style='border: 0; border-top: 2px solid #bce0ff; margin: 15px 0;'>
                        <b style='font-size: 20px;'>ИТОГО: <span style='float: right; color: #000;'>{report['total_revenue']} сом</span></b>
                    </div>
                </div>
                
                <div style='background: #f6fff8; padding: 25px; border-radius: 10px; flex: 1; border: 1px solid #c3e6cb; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);'>
                    <b style='color: #1e7e34; font-size: 18px;'>📈 ПРИБЫЛЬ</b><br><br>
                    <div style='font-size: 16px;'>
                        Себестоимость: <span style='float: right;'>{report['bar_cost']} сом</span><br>
                        Кол-во товаров: <span style='float: right;'>{report['items_count']} ед.</span><br>
                        <hr style='border: 0; border-top: 2px solid #c3e6cb; margin: 15px 0;'>
                        <b style='font-size: 20px;'>МАРЖА: <span style='float: right; color: #27ae60;'>+{report['bar_profit']} сом</span></b>
                    </div>
                </div>
            </div>

            <div style='display: flex; gap: 30px;'>
                <div style='flex: 1;'>
                    <h3 style='color: #2c3e50; border-left: 5px solid #3498db; padding-left: 10px;'>🎱 Доход по столам</h3>
                    <table style='width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #ddd; font-size: 15px;'>
                        <thead style='background: #f1f1f1;'>
                            <tr>
                                <th style='padding: 12px; text-align: left; color: #000;'>Стол/Консоль</th>
                                <th style='padding: 12px; text-align: right; color: #000;'>Всего</th>
                            </tr>
                        </thead>
                        <tbody>{resource_rows if resource_rows else "<tr><td colspan='2' style='padding:20px; color:#666;'>Нет данных</td></tr>"}</tbody>
                    </table>
                </div>

                <div style='flex: 1.5;'>
                    <h3 style='color: #2c3e50; border-left: 5px solid #2ecc71; padding-left: 10px;'>🛒 Детализация товаров</h3>
                    <table style='width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #ddd; font-size: 15px;'>
                        <thead style='background: #f1f1f1;'>
                            <tr>
                                <th style='padding: 12px; text-align: left; color: #000;'>Товар</th>
                                <th style='padding: 12px; text-align: center; color: #000;'>Кол-во</th>
                                <th style='padding: 12px; text-align: right; color: #000;'>Выручка</th>
                                <th style='padding: 12px; text-align: right; color: #000;'>Маржа</th>
                            </tr>
                        </thead>
                        <tbody>{product_rows if product_rows else "<tr><td colspan='4' style='padding:20px; color:#666;'>Нет данных</td></tr>"}</tbody>
                    </table>
                </div>
            </div>
        </div>
        """
        return mark_safe(html_content)
    get_full_report.short_description = "Аналитический отчет"


# 3. Session Admin
@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'resource', 'shift', 'get_local_start_time', 'get_table_only_cost', 'is_active', 'created_by')
    
    def get_local_start_time(self, obj):
        if obj.start_time:
            return date_format(timezone.localtime(obj.start_time), format="H:i (d.m)", use_l10n=True)
        return "-"
    get_local_start_time.short_description = "Время начала"
    get_local_start_time.admin_order_field = 'start_time'

    def get_readonly_fields(self, request, obj=None):
        base_readonly = ['get_table_only_cost', 'get_bar_total_cost']
        if obj:
            return base_readonly + ['start_time', 'end_time', 'resource', 'shift', 'created_by', 'mode', 'prepaid_minutes']
        return base_readonly

    fields = (
        'resource', 'shift', 'start_time', 'end_time', 
        'get_table_only_cost', 'get_bar_total_cost', 
        'is_active', 'created_by', 'mode', 'prepaid_minutes'
    )
    
    def get_bar_total_cost(self, obj):
        if obj and obj.id:
            total = sum(item.total_price() for item in obj.items.all())
            return format_html('<b style="color: #27ae60; font-size: 1.2em;">{:.2f} сом</b>', total)
        return "0.00 сом"
    get_bar_total_cost.short_description = "Итого по Бару"

    list_filter = ('shift', 'is_active', 'mode', 'resource')
    search_fields = ('resource__name', 'created_by__username')
    autocomplete_fields = ['shift'] 
    inlines = [SessionItemInline, BillInline]

    def get_table_only_cost(self, obj):
        if obj.is_active:
            now = timezone.now()
            diff = now - obj.start_time
            mins = Decimal(diff.total_seconds() / 60)
            price_min = Decimal(obj.resource.price_per_hour) / Decimal(60)
            amount_str = f"{round(mins * price_min, 2):.2f}"
            return format_html('<b style="color: #3498db; font-size: 1.2em;">{} сом (текущая)</b>', amount_str)
        else:
            bill = Bill.objects.filter(session=obj).first()
            if bill:
                items_total = sum(item.total_price() for item in obj.items.all())
                table_cost = bill.total_amount - Decimal(items_total)
                # ✅ FIX: Explicitly format it to a plain string first, then use standard {} placeholder
                amount_str = f"{table_cost:.2f}"
                return format_html('<b style="font-size: 1.2em;">{} сом</b>', amount_str)
        return "0.00 сом"


# 4. Bill Admin 
@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'get_table_cost', 'get_items_cost', 'total_amount')
    readonly_fields = ('get_details_html', 'total_amount', 'session')

    def get_table_cost(self, obj):
        items_total = sum(item.total_price() for item in obj.session.items.all())
        table_cost = obj.total_amount - Decimal(items_total)
        return f"{table_cost:.2f} сом"
    get_table_cost.short_description = "Стоимость стола"

    def get_items_cost(self, obj):
        items_total = sum(item.total_price() for item in obj.session.items.all())
        return f"{items_total:.2f} сом"
    get_items_cost.short_description = "Сумма бара"

    def get_details_html(self, obj):
        session = obj.session
        items = session.items.all()
        items_total = sum(item.total_price() for item in items)
        table_cost = obj.total_amount - Decimal(items_total)
        local_start = timezone.localtime(session.start_time)
        
        html = f"""
        <div style="background: #fff; padding: 20px; border: 1px solid #ccc; border-radius: 8px; max-width: 500px; font-family: monospace; color: #000;">
            <h3 style="text-align: center; border-bottom: 2px dashed #000; padding-bottom: 10px; color: #000;">ДЕТАЛИЗАЦИЯ СЧЕТА #{obj.id}</h3>
            <p><b>Ресурс:</b> {session.resource.name}</p>
            <p><b>Время начала:</b> {local_start.strftime('%H:%M')}</p>
            <hr style="border: 0; border-top: 1px dashed #000;">
            <table style="width: 100%;">
                <tr>
                    <td style="padding: 5px 0; color: #000;">Услуга: Время</td>
                    <td style="text-align: right; color: #000;">{table_cost:.2f} сом</td>
                </tr>
        """
        for item in items:
            html += f"""
                <tr>
                    <td style="padding: 5px 0; color: #000;">{item.product.name} (x{item.quantity})</td>
                    <td style="text-align: right; color: #000;">{item.total_price():.2f} сом</td>
                </tr>
            """
        html += f"""
            </table>
            <hr style="border: 0; border-top: 2px solid #000; margin-top: 10px;">
            <div style="font-size: 1.4em; font-weight: bold; display: flex; justify-content: space-between; color: #000;">
                <span>ИТОГО:</span>
                <span>{obj.total_amount} сом</span>
            </div>
        </div>
        """
        return mark_safe(html)
    get_details_html.short_description = "Печатная форма"


# 5. Resource Admin
@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'price_per_hour')


# 6. Product Admin
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'cost_price', 'price', 'stock', 'get_margin', 'get_total_cost_value', 'get_total_sales_value')
    # list_editable = ('is_active',)
    def get_readonly_fields(self, request, obj=None):
        if obj: 
            return ['name', 'stock']
        return []

    def get_margin(self, obj):
        margin = obj.price - (obj.cost_price or 0)
        return f"{margin} сом"
    get_margin.short_description = "Наценка"

    def get_total_cost_value(self, obj):
        total = (obj.stock or 0) * (obj.cost_price or 0)
        return f"{int(total)} сом"
    get_total_cost_value.short_description = "Итого (Закуп)"

    def get_total_sales_value(self, obj):
        total = (obj.stock or 0) * obj.price
        return f"{int(total)} сом"
    get_total_sales_value.short_description = "Итого (Продажа)"

    def changelist_view(self, request, extra_context=None):
        totals = Product.objects.aggregate(
            all_bar_cost=Sum(F('stock') * F('cost_price')),
            all_bar_sales=Sum(F('stock') * F('price'))
        )
        cost_total = math.ceil(totals['all_bar_cost'] or 0)
        sales_total = math.ceil(totals['all_bar_sales'] or 0)
        profit_total = sales_total - cost_total

        summary_message = format_html(
            "📊 <b>ОТЧЕТ ПО СКЛАДУ:</b> "
            "Вложено (Закуп): <span style='color: #d9534f; font-weight: bold;'>{} сом</span> | "
            "Выручка (Продажа): <span style='color: #5cb85c; font-weight: bold;'>{} сом</span> | "
            "Потенциальная прибыль: <span style='color: #0275d8; font-weight: bold;'>{} сом</span>",
            cost_total, sales_total, profit_total
        )
        storage = messages.get_messages(request)
        for _ in storage: pass 
        messages.info(request, summary_message)

        extra_context = extra_context or {}
        extra_context['summary_text'] = summary_message
        return super().changelist_view(request, extra_context=extra_context)