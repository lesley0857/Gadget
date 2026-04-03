from django.contrib import admin
from django.urls import path,include
from catalog.views import ProductListView, ProductCreateView
from orders.views import CreateOrderView
from webhooks.views import paystack_webhook
from django.conf.urls.static import static
from django.conf import settings

from accounts.views import *
from cart.views import *
from payments.views import *
from disputes.views import *
from orders.views import *

urlpatterns = [
    path("admin/", admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('cart/', cart_view, name='cart'),
    path('cart/add/<int:listing_id>/', add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:listing_id>/', remove_from_cart, name='remove_from_cart'),
    path('cart/update/', update_cart, name='update_cart'),
    path('checkout/', checkout_view, name='checkout'),
    path('orders/dispute/<int:item_id>/', dispute_page, name='dispute_page'),
    path("orders/json/", user_orders_json, name="user_orders_json"),
    path("pay/", initiate_payment, name="initiate_payment"),
    path("payment/verify/", verify_payment, name="verify_payment"),
    path("payment_success/", payment_success, name="payment_success"),
    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('', home, name='home'),

    path('product/<int:product_id>/', product_detail, name='product_detail'),

    path("products/", ProductListView.as_view(),name='products'),
    path("products/create/", ProductCreateView.as_view()),

    path("orders/create/", CreateOrderView.as_view()),

    path("webhooks/paystack/", paystack_webhook),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)