from django.contrib import admin
from .models import Resource, Product, Session, Bill, SessionItem, Shift
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.db.models import Sum, Count, F
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.formats import date_format
from decimal import Decimal



admin.site.site_header = "Панель управления Billiard POS"
admin.site.site_title = "Billiard POS Админ"
admin.site.index_title = "Добро пожаловать в систему управления"

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
            # Используем формат Django для красивой даты на русском
            return date_format(obj.start_time, format="d E Y (H:i)", use_l10n=True)
        return "Неизвестно"
    
    get_shift_date.short_description = "Дата/Время начала"

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

        from django.utils import timezone
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

# 3. Session Admin
@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    # 1. Поля в списке (уже есть)
    list_display = ('id', 'resource', 'shift', 'start_time', 'get_table_only_cost', 'is_active', 'created_by')
    
    # 2. Поля внутри карточки (ДОБАВЛЯЕМ СЮДА)
    readonly_fields = ('start_time', 'get_table_only_cost', 'get_bar_total_cost') # Добавьте это, если хотите видеть поле внутри
    
    # Чтобы поле красиво стояло в форме, можно настроить fields:
    fields = ('resource', 'shift', 'start_time', 'end_time', 'get_table_only_cost', 'is_active', 'created_by', 'mode', 'prepaid_minutes')
    def get_bar_total_cost(self, obj):
        total = sum(item.total_price() for item in obj.items.all())
        return format_html('<b style="color: #27ae60; font-size: 1.2em;">{:.2f} сом</b>', total)

    get_bar_total_cost.short_description = "Итого по Бару"
    list_filter = ('shift', 'is_active', 'mode', 'resource')
    search_fields = ('resource__name', 'created_by__username')
    autocomplete_fields = ['shift'] 
    inlines = [SessionItemInline, BillInline]

    def get_table_only_cost(self, obj):
        """Рассчитывает стоимость только за время (без бара)"""
        if obj.is_active:
            now = timezone.now()
            diff = now - obj.start_time
            mins = Decimal(diff.total_seconds() / 60)
            price_min = Decimal(obj.resource.price_per_hour) / Decimal(60)
            
            # Сначала форматируем число в строку
            amount_str = f"{round(mins * price_min, 2):.2f}"
            
            # Затем передаем готовую строку в format_html
            return format_html(
                '<b style="color: #3498db; font-size: 1.2em;">{} сом (текущая)</b>', 
                amount_str
            )
        else:
            bill = Bill.objects.filter(session=obj).first()
            if bill:
                items_total = sum(item.total_price() for item in obj.items.all())
                table_cost = bill.total_amount - Decimal(items_total)
                amount_str = f"{table_cost:.2f}"
                return format_html('<b style="font-size: 1.2em;">{} сом</b>', amount_str)
        return "0.00 сом"

    get_table_only_cost.short_description = "Стоимость времени (Бильярд)"
# 4. Bill Admin 
@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    # Теперь в списке видны отдельно Бар и Стол
    list_display = ('id', 'session', 'get_table_cost', 'get_items_cost', 'total_amount')
    readonly_fields = ('get_details_html', 'total_amount', 'session')
    exclude = ()

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
        """Генерирует HTML-квитанцию внутри карточки счета"""
        session = obj.session
        items = session.items.all()
        items_total = sum(item.total_price() for item in items)
        table_cost = obj.total_amount - Decimal(items_total)
        
        html = f"""
        <div style="background: #fff; padding: 20px; border: 1px solid #ccc; border-radius: 8px; max-width: 500px; font-family: monospace;">
            <h3 style="text-align: center; border-bottom: 2px dashed #000; padding-bottom: 10px;">ДЕТАЛИЗАЦИЯ СЧЕТА #{obj.id}</h3>
            <p><b>Ресурс:</b> {session.resource.name}</p>
            <p><b>Время начала:</b> {session.start_time.strftime('%H:%M')}</p>
            <hr style="border: 0; border-top: 1px dashed #000;">
            <table style="width: 100%;">
                <tr>
                    <td style="padding: 5px 0;">Услуга: Время</td>
                    <td style="text-align: right;">{table_cost:.2f} сом</td>
                </tr>
        """
        for item in items:
            html += f"""
                <tr>
                    <td style="padding: 5px 0;">{item.product.name} (x{item.quantity})</td>
                    <td style="text-align: right;">{item.total_price():.2f} сом</td>
                </tr>
            """
        html += f"""
            </table>
            <hr style="border: 0; border-top: 2px solid #000; margin-top: 10px;">
            <div style="font-size: 1.4em; font-weight: bold; display: flex; justify-content: space-between;">
                <span>ИТОГО:</span>
                <span>{obj.total_amount} сом</span>
            </div>
        </div>
        """
        return mark_safe(html)
    
    get_details_html.short_description = "Печатная форма"

# 5. Resource & Product Admin
@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'price_per_hour')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # Added cost_price to display and editable fields
    list_display = ('name', 'cost_price', 'price', 'stock', 'get_margin') 
    list_editable = ('cost_price', 'price', 'stock')
    
    def get_margin(self, obj):
        # Shows profit per item
        margin = obj.price - (obj.cost_price or 0)
        return f"{margin} сом"
    get_margin.short_description = "Наценка"