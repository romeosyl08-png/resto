from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from shop import views as shop_views
from django.conf.urls.static import static


urlpatterns = [


    # Admin Django classique
    path('admin/', admin.site.urls),


    # Site public (toutes les URLs de l’app shop)
    path('', include('shop.urls', namespace='shop')),
    path('comptes', include('comptes.urls', namespace='comptes')),
    path('orders', include('orders.urls', namespace='orders')),
    path('staff', include('staff.urls', namespace='staff')),
    path("api/marketing/", include("marketing.urls")),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)