from django.contrib import admin
from .models import Resource, Product, Session, ResourceUsage, OrderItem, Bill, SessionItem

# 1. Setup Inlines (This lets you see details inside the Session page)
class SessionItemInline(admin.TabularInline):
    model = SessionItem
    extra = 0
    readonly_fields = ('total_price',)

class BillInline(admin.StackedInline):
    model = Bill
    extra = 0
    can_delete = False

# 2. Register the Session with Inlines
@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'resource', 'start_time', 'end_time', 'mode', 'is_active', 'created_by')
    list_filter = ('is_active', 'mode', 'resource')
    search_fields = ('resource__name',)
    # This line connects the details!
    inlines = [SessionItemInline, BillInline]

# 3. Register everything else ONCE
admin.site.register(Resource)
admin.site.register(Product)
admin.site.register(ResourceUsage)
admin.site.register(OrderItem)
admin.site.register(Bill)