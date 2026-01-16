from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    raw_id_fields = ("meal",)
    fields = ("meal", "variant_code", "quantity", "unit_price", "subtotal_display")
    readonly_fields = ("subtotal_display",)

    def subtotal_display(self, obj):
        if not obj.pk:
            return "-"
        return obj.subtotal()
    subtotal_display.short_description = "Sous-total"

    # Optionnel: verrouiller édition si commande non modifiable
    def has_change_permission(self, request, obj=None):
        if obj and hasattr(obj, "is_editable") and not obj.is_editable():
            return False
        return super().has_change_permission(request, obj)

    def has_add_permission(self, request, obj=None):
        if obj and hasattr(obj, "is_editable") and not obj.is_editable():
            return False
        return super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and hasattr(obj, "is_editable") and not obj.is_editable():
            return False
        return super().has_delete_permission(request, obj)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]

    # Adresse visible en liste
    list_display = (
        "id", "customer_name", "phone", "address_short","address_detail",
        "user", "status", "subtotal", "discount_total", "total", "created_at"
    )
    list_filter = ("status", "created_at", "user")
    search_fields = ("id", "customer_name", "phone", "user__username", "address")

    readonly_fields = ("subtotal", "discount_total", "total", "created_at")

    fieldsets = (
        ("Client", {"fields": ("user", "customer_name", "phone", "address","address_detail")}),
        ("Statut", {"fields": ("status",)}),
        ("Montants", {"fields": ("subtotal", "discount_total", "total")}),
        ("Meta", {"fields": ("created_at",)}),
    )

    actions = ("mark_confirmed", "mark_delivered", "mark_canceled")

    def address_short(self, obj):
        a = (obj.address or "").strip()
        return a[:40] + "…" if len(a) > 40 else a
    address_short.short_description = "Adresse"
    def address_detail_short(self, obj):
        s = (obj.address_detail or "").strip()
        return s[:40] + "…" if len(s) > 40 else s
    address_detail_short.short_description = "Adresse exacte"

# puis mets address_detail_short dans list_display


    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        obj = form.instance
        if hasattr(obj, "recompute_subtotal"):
            obj.recompute_subtotal()
            obj.save(update_fields=["subtotal", "total"])

    @admin.action(description="Marquer comme Confirmée")
    def mark_confirmed(self, request, queryset):
        queryset.update(status="confirmed")

    @admin.action(description="Marquer comme Livrée")
    def mark_delivered(self, request, queryset):
        queryset.update(status="delivered")

    @admin.action(description="Marquer comme Annulée")
    def mark_canceled(self, request, queryset):
        queryset.update(status="canceled")


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "meal", "variant_code", "quantity", "unit_price", "subtotal_display")
    list_filter = ("variant_code",)
    raw_id_fields = ("order", "meal")
    search_fields = ("order__id", "meal__name", "variant_code")

    def subtotal_display(self, obj):
        return obj.subtotal()
    subtotal_display.short_description = "Sous-total"
