from django.contrib.sitemaps import Sitemap
from .models import Meal

class MealSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return Meal.objects.filter(is_active=True)

    def location(self, obj):
        # Assure-toi que tu as get_absolute_url() dans Meal
        return obj.get_absolute_url()
