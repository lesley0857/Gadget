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
from services.views import *
from remarobeprojects.views import *
from blog.views import *
from logistics.views import *

urlpatterns = [
    path("admin/", admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path("summernote/", include("django_summernote.urls")),
    path('cart/', cart_view, name='cart'),
    path('about-us/', about_us, name='about_us'),
    path('cart/add/<int:listing_id>/', add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:listing_id>/', remove_from_cart, name='remove_from_cart'),
    path("cart/summary/", cart_summary, name="cart_summary"),
    path('cart/update/', update_cart, name='update_cart'),
    
    path("negotiation/request/",negotiate_cart,name="negotiate_cart"),
    path("negotiation/approve/<slug:pk>/",approve_negotiation,name="approve_negotiation"),
    path("negotiation/pay/<uuid:token>/",pay_negotiation_secure,name="pay_negotiation_secure"),
    path("negotiation/expired/",quotation_expired,name="quotation_expired"),
    path("quotation/<str:code>/pay/",pay_negotiation,name="pay_negotiation"),

    path("negotiations/dashboard/",negotiation_dashboard,name="negotiation_dashboard"),
    path("negotiations/detail/<int:pk>/",admin_negotiation_detail,name="admin_negotiation_detail"),


    path("admin-negotiation/",negotiation_lookup,name="negotiation_lookup"),
    path("admin-negotiation/<int:pk>/",admin_negotiation_detail,name="admin_negotiation_detail"),
    path("negotiation/<slug:code>/",negotiation_detail,name="negotiation_detail"),
    path("user_negotiation_ready_view/<slug:code>/",user_negotiation_ready_view,name="user_negotiation_ready_view"),
    path("negotiation/payment/verify/",verify_negotiated_payment,name="verify_negotiated_payment"),


    path("orders/",orders_page,name="orders_page"),
    path("orders/detail/<slug:order_number>/",order_detail,name="order_detail"),
    path("json/",orders_json,name="orders_json"),
    path("checkout/", checkout_view, name="checkout"),
    path('orders/dispute/<int:item_id>/', dispute_page, name='dispute_page'),
    path("orders/<slug:order_number>/track/",track_order,name="track_order"),
    path("pay/", initiate_payment, name="initiate_payment"),
    path("payment/verify/", verify_payment, name="verify_payment"),
    path("payment_success/", payment_success, name="payment_success"),
    path("resume-payment/<str:reference>/", resume_payment, name="resume_payment"),
    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('', home, name='home'),
    path("blog/<slug:slug>/",blog_detail,name="blog_detail"),
    path('project/<slug:slug>/', project_detail, name='project_detail'),
    
    path("delivery/dashboard/", delivery_dashboard, name="delivery_dashboard"),

    path("accounts/profile/", profile_view, name="profile"),
    path("profile/update/", update_profile, name="update_profile"),

    # 🏪 VENDOR
    path("vendor/signup/", vendor_signup, name="vendor_signup"),
    path("vendor/dashboard/", vendor_dashboard, name="vendor_dashboard"),
    path("vendor/update/", vendor_update, name="vendor_update"),
    path("vendor/delete/", vendor_delete, name="vendor_delete"),
    path('product/<str:name>/', product_detail, name='product_detail'),

    path("category/<str:name>/",category_products, name="category_products"),
    path("search/", search_products, name="search_products"),
    path("search-suggestions/", search_suggestions, name="search_suggestions"),

    path('services/', services_page,name='services'),
    path('services/<slug:slug>/', service_detail,name='service_detail'),

    path("webhooks/paystack/", paystack_webhook),
]
handler404 = 'accounts.views.custom_404'
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

