from django.contrib import admin
from .models import Category, Meal, MealVariant, Supplement
from django.utils.html import format_html


class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)





class MealVariantInline(admin.TabularInline):
    model = MealVariant
    extra = 0
    fields = ('code', 'label', 'price', 'stock', 'is_active', 'image', 'image_preview')
    readonly_fields = ('image_preview',)

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:60px;height:60px;object-fit:cover;border-radius:6px;" />',
                obj.image.url
            )
        return "—"

    image_preview.short_description = "Aperçu"

@admin.register(Meal)
class MealAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MealVariantInline]
    list_display = ("name", "category", "is_active", "stock")
    list_filter = ("is_active", "category")
    search_fields = ("name",)
    filter_horizontal = ("supplements",)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "supplements":
            kwargs["queryset"] = Supplement.objects.filter(is_active=True)
        return super().formfield_for_manytomany(db_field, request, **kwargs)



@admin.register(Supplement)
class SupplementAdmin(admin.ModelAdmin):
    list_display = (
        "image_preview",
        "name",
        "type",
        "price",
        "is_active",
    )
    list_filter = ("type", "is_active",)
    search_fields = ("name",)
    ordering = ("name",)
    readonly_fields = ("image_preview",)

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:60px;height:60px;object-fit:cover;border-radius:6px;" />',
                obj.image.url
            )
        return "—"

    image_preview.short_description = "Image"


admin.site.register(Category)
@admin.register(MealVariant)
class MealVariantAdmin(admin.ModelAdmin):
    list_display = ('meal', 'code', 'label', 'price', 'stock', 'is_active', 'image_preview')
    list_filter = ('is_active', 'meal')
    search_fields = ('meal__name', 'label')
    readonly_fields = ('image_preview',)

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width:200px;max-height:200px;" />',
                obj.image.url
            )
        return "—"

    image_preview.short_description = "Aperçu"


