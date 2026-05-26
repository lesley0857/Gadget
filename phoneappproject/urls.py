from django.contrib import admin
from django.urls import path,include
from webhooks.views import paystack_webhook
from django.conf.urls.static import static
from django.conf import settings
import accounts
from accounts.views import *
from cart.views import *
from payments.views import *
from disputes.views import *
from orders.views import *
from catalog.views import *

urlpatterns = [
    path("admin/", admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('cart/', cart_view, name='cart'),
    path('cart/add/<int:listing_id>/', add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:listing_id>/', remove_from_cart, name='remove_from_cart'),
    path("cart/summary/", cart_summary, name="cart_summary"),
    path('cart/update/', update_cart, name='update_cart'),
    path('checkout/', checkout_view, name='checkout'),
    path('orders/dispute/<int:item_id>/', dispute_page, name='dispute_page'),
    path("orders/json/", user_orders_json, name="user_orders_json"),
    path("pay/", initiate_payment, name="initiate_payment"),
    path("payment/verify/", verify_payment, name="verify_payment"),
    path("payment_success/", payment_success, name="payment_success"),
    path("resume-payment/<str:reference>/", resume_payment, name="resume_payment"),
    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('', home, name='home'),

    path("accounts/profile/", profile_view, name="profile"),
    path("profile/update/", update_profile, name="update_profile"),

    # 🏪 VENDOR
    path("vendor/signup/", vendor_signup, name="vendor_signup"),
    path("vendor/dashboard/", vendor_dashboard, name="vendor_dashboard"),
    path("vendor/update/", vendor_update, name="vendor_update"),
    path("vendor/delete/", vendor_delete, name="vendor_delete"),
    path('product/<int:product_id>/', product_detail, name='product_detail'),

    path("category/<int:id>/", category_products, name="category_products"),
    path("search/", search_products, name="search_products"),
    path("search-suggestions/", search_suggestions, name="search_suggestions"),
    path("products/", ProductListView.as_view(),name='products'),
    path("products/create/", ProductCreateView.as_view()),

    path("orders/create/", CreateOrderView.as_view()),

    path(
        "shipping/request/",
        request_shipping_negotiation,
        name="request_shipping_negotiation"
    ),

    path(
        "shipping/negotiated/<str:code>/",
        negotiated_checkout,
        name="negotiated_checkout"
    ),

    path(
        "shipping/pay/<str:code>/",
        pay_negotiated_shipping,
        name="pay_negotiated_shipping"
    ),

    path("webhooks/paystack/", paystack_webhook),
]
handler404 = 'accounts.views.custom_404'
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)