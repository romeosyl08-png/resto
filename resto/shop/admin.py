from django.contrib import admin
from .models import Category, Meal, MealVariant


class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)





class MealVariantInline(admin.TabularInline):
    model = MealVariant
    extra = 0

@admin.register(Meal)
class MealAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MealVariantInline]
    list_display = ("name", "category", "is_active", "stock")

admin.site.register(Category)
admin.site.register(MealVariant)



