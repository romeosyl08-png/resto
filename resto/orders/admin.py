from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    raw_id_fields = ('meal',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_name', 'phone', 'user', 'status', 'total', 'created_at')
    list_filter = ('status', 'created_at', 'user')
    search_fields = ('customer_name', 'phone', 'user__username')
    inlines = [OrderItemInline]
    readonly_fields = ('total', 'created_at')



@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'meal', 'quantity', 'unit_price')
    raw_id_fields = ('order', 'meal')