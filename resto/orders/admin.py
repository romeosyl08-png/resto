from django.contrib import admin
from .models import Order, OrderItem, OrderItemSupplement, Address


# ============================================================================
# INLINE pour Address
# ============================================================================
class AddressInline(admin.TabularInline):
    """Afficher/modifier les adresses directement depuis le profil utilisateur"""
    model = Address
    extra = 0
    fields = ("room", "sector", "other", "other_detail", "delivery_paid", "created_at")
    readonly_fields = ("created_at",)
    
    def has_delete_permission(self, request, obj=None):
        # On peut toujours supprimer une adresse
        return True


# ============================================================================
# ADMIN pour Address (gestion standalone)
# ============================================================================
@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = (
        "id", 
        "user", 
        "address_display", 
        "delivery_paid", 
        "created_at"
    )
    list_filter = ("other", "delivery_paid", "sector", "room", "created_at")
    search_fields = ("user__username", "user__email", "other_detail", "room", "sector")
    readonly_fields = ("created_at",)
    
    fieldsets = (
        ("Utilisateur", {
            "fields": ("user",)
        }),
        ("Adresse interne", {
            "fields": ("room", "sector"),
            "description": "Remplir uniquement si c'est une adresse interne (campus)"
        }),
        ("Autre endroit", {
            "fields": ("other", "other_detail", "delivery_paid"),
            "description": "Cocher 'other' pour une adresse externe (Yango/Glovo)"
        }),
        ("Métadonnées", {
            "fields": ("created_at",)
        }),
    )
    
    def address_display(self, obj):
        """Affiche l'adresse de manière lisible"""
        if obj.other:
            detail = obj.other_detail[:50] + "..." if len(obj.other_detail) > 50 else obj.other_detail
            return f"🚕 Autre endroit: {detail}"
        return f"🏢 {obj.room} - {obj.sector}"
    
    address_display.short_description = "Adresse"


# ============================================================================
# INLINE pour OrderItemSupplement
# ============================================================================
class OrderItemSupplementInline(admin.TabularInline):
    model = OrderItemSupplement
    extra = 1
    raw_id_fields = ("supplement",)
    fields = ("supplement", "quantity", "unit_price", "subtotal_display")
    readonly_fields = ("subtotal_display",)

    def subtotal_display(self, obj):
        if not obj.pk:
            return "-"
        return f"{obj.subtotal()} FCFA"

    subtotal_display.short_description = "Sous-total"


# ============================================================================
# INLINE pour OrderItem
# ============================================================================
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    raw_id_fields = ("meal",)
    fields = ("meal", "variant_code", "quantity", "unit_price", "supplements_summary", "subtotal_display")
    readonly_fields = ("supplements_summary", "subtotal_display")

    def supplements_summary(self, obj):
        """Affiche un résumé des suppléments"""
        if not obj.pk:
            return "-"
        sups = obj.supplements.all()
        if not sups:
            return "Aucun"
        return ", ".join([f"{s.supplement.name} x{s.quantity}" for s in sups])
    
    supplements_summary.short_description = "Suppléments"

    def subtotal_display(self, obj):
        if not obj.pk:
            return "-"
        return f"{obj.subtotal()} FCFA"

    subtotal_display.short_description = "Sous-total"

  
    def has_change_permission(self, request, obj=None):
        if obj and isinstance(obj, OrderItem) and not obj.order.is_editable():
            return False
        return super().has_change_permission(request, obj)

    def has_add_permission(self, request, obj=None):
        if obj and isinstance(obj, OrderItem) and not obj.order.is_editable():
            return False
        return super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and isinstance(obj, OrderItem) and not obj.order.is_editable():
            return False
        return super().has_delete_permission(request, obj)



# ============================================================================
# ADMIN pour Order
# ============================================================================
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline] 

    list_display = (
        "id", 
        "customer_name", 
        "phone", 
        "address_display",  # ✅ Nouvelle méthode pour afficher l'adresse
        "user", 
        "status", 
        "subtotal", 
        "discount_total", 
        "total", 
        "created_at"
    )
    list_filter = ("status", "created_at", "user")
    search_fields = (
        "id", 
        "customer_name", 
        "phone", 
        "user__username", 
        "address",  # Texte de l'adresse
        "address_detail"  # Détails supplémentaires
    )

    readonly_fields = ("subtotal", "discount_total", "total", "created_at")

    fieldsets = (
        ("Client", {
            "fields": ("user", "customer_name", "phone")
        }),
        ("Adresse de livraison", {
            "fields": ("address", "address_detail"),
            "description": "Ces champs contiennent le texte de l'adresse au moment de la commande"
        }),
        ("Code promo", {
            "fields": ("promo_code",)
        }),
        ("Statut", {
            "fields": ("status",)
        }),
        ("Montants", {
            "fields": ("subtotal", "discount_total", "total")
        }),
        ("Métadonnées", {
            "fields": ("created_at",)
        }),
    )

    actions = ["mark_confirmed", "mark_delivered", "mark_canceled"]

    def address_display(self, obj):
        """
        Affiche l'adresse de manière condensée dans la liste
        Format: "L1 - IMERTEL" ou "Autre endroit: [détails]"
        """
        addr = (obj.address or "").strip()
        detail = (obj.address_detail or "").strip()
        
        # Si c'est une adresse "autre endroit"
        if "Autre endroit" in addr or "livraison" in addr.lower():
            # Affiche les détails (tronqués si trop longs)
            if detail:
                return f"🚕 {detail[:30]}..." if len(detail) > 30 else f"🚕 {detail}"
            return "🚕 Autre endroit"
        
        # Adresse interne
        if addr:
            return f"🏢 {addr[:35]}..." if len(addr) > 35 else f"🏢 {addr}"
        
        return "-"
    
    address_display.short_description = "Adresse"

    def save_related(self, request, form, formsets, change):
        """Recalcule les totaux après modification des items"""
        super().save_related(request, form, formsets, change)
        obj = form.instance
        if hasattr(obj, "recompute_subtotal"):
            obj.refresh_from_db()  # Assurer que les items modifiés sont vus
            obj.recompute_subtotal()
            obj.save(update_fields=["subtotal", "total"])

    @admin.action(description="✓ Marquer comme Confirmée")
    def mark_confirmed(self, request, queryset):
        updated = queryset.filter(status="pending").update(status="confirmed", is_delivered=False)
        self.message_user(request, f"{updated} commande(s) confirmée(s).")

    @admin.action(description="✓✓ Marquer comme Livrée")
    def mark_delivered(self, request, queryset):
        updated = 0
        for order in queryset.filter(status="confirmed"):
            order.status = "delivered"
            order.is_delivered = True
            order.save(update_fields=["status", "is_delivered"])
            updated += 1
        self.message_user(request, f"{updated} commande(s) livrée(s).")

    @admin.action(description="✗ Marquer comme Annulée")
    def mark_canceled(self, request, queryset):
        updated = 0
        for order in queryset.filter(status__in=["pending", "confirmed"]):
            order.status = "canceled"
            order.is_delivered = False
            order.save(update_fields=["status", "is_delivered"])
            updated += 1
        self.message_user(request, f"{updated} commande(s) annulée(s).")


# ============================================================================
# ADMIN pour OrderItem (optionnel, pour gestion standalone)
# ============================================================================
@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "order", 
        "meal", 
        "variant_code", 
        "quantity", 
        "unit_price", 
        "supplements_count",
        "subtotal_display"
    )
    list_filter = ("variant_code", "order__status")
    raw_id_fields = ("order", "meal")
    search_fields = ("order__id", "meal__name", "variant_code")
    
    inlines = [OrderItemSupplementInline]

    def supplements_count(self, obj):
        """Compte le nombre de suppléments"""
        count = obj.supplements.count()
        return f"{count} supplément(s)" if count > 0 else "Aucun"
    
    supplements_count.short_description = "Suppléments"

    def subtotal_display(self, obj):
        return f"{obj.subtotal()} FCFA"
    
    subtotal_display.short_description = "Sous-total"


# ============================================================================
# ADMIN pour OrderItemSupplement (optionnel, pour gestion standalone)
# ============================================================================
@admin.register(OrderItemSupplement)
class OrderItemSupplementAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order_item",
        "supplement",
        "quantity",
        "unit_price",
        "subtotal_display",
    )
    list_filter = ("supplement",)
    raw_id_fields = ("order_item", "supplement")
    search_fields = ("order_item__order__id", "supplement__name")

    def subtotal_display(self, obj):
        return f"{obj.subtotal()} FCFA"

    subtotal_display.short_description = "Sous-total"
