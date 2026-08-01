from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from shop import sitemaps
from shop import views as shop_views
from django.conf.urls.static import static

from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView


sitemaps = {
    'meals': sitemaps.MealSitemap,
}


urlpatterns = [


    # Admin Django classique
    path('admin/', admin.site.urls),


    # Site public (toutes les URLs de l’app shop)
    path('', include('shop.urls', namespace='shop')),
    path('comptes/', include('comptes.urls', namespace='comptes')),
    path('orders/', include('orders.urls', namespace='orders')),
    path('staff/', include('staff.urls', namespace='staff')),
    path("api/marketing/", include("marketing.urls")),

    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    path('robots.txt', TemplateView.as_view(template_name="robots.txt", content_type='text/plain')),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)