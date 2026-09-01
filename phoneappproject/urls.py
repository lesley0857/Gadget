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
from solar import views
from logistics.views import *

from django.contrib import admin

admin.site.site_header = "REMAROBE Administration"
admin.site.site_title = "REMAROBE Admin"
admin.site.index_title = "Welcome to REMAROBE Administration"

handler404 = "accounts.views.custom_404"

urlpatterns = [
    path("remarobe_secure_admin/", admin.site.urls),
    path('accounts/login/', login_view, name='account_login'),
    path('accounts/signup/', register_view, name='account_signup'),

    path('accounts/', include('allauth.urls')),
    path("summernote/", include("django_summernote.urls")),
    path('cart/', cart_view, name='cart'),
    path('about-us/', about_us, name='about_us'),
    path('privacy-policy/', privacy_policy, name='privacy_policy'),
    path('terms-and-conditions/', terms_and_conditions, name='terms_and_conditions'),
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
    path("search/suggestions/", search_suggestions, name="search_suggestions"),

    path('services/', services_page,name='services'),
    path('services/<slug:slug>/', service_detail,name='service_detail'),

   

    # ==============================================================
    # MAIN SOLAR DESIGN
    # ==============================================================

    path("dashboard/", views.solar_dashboard, name="dashboard"),

    path(
        "design/",
        views.solar_design,
        name="solar_design",
    ),
    path("tools/in-progress/", views.tool_in_progress, name="tool_in_progress"),
    path("earthing/", views.earthing_assessment, name="earthing_assessment"),


    path(
        "design/<int:design_id>/",
        views.solar_design_result,
        name="design_result",
    ),

    path(
        "design/<int:design_id>/update/",
        views.update_solar_design,
        name="update_design",
    ),


    # ==============================================================
    # PROJECTS
    # ==============================================================

    path(
        "projects/",
        views.solar_design_history,
        name="design_history",
    ),

    path(
        "projects/<int:design_id>/",
        views.project_details,
        name="project_details",
    ),

    path(
        "projects/<int:design_id>/favorite/",
        views.favorite_design,
        name="favorite_design",
    ),

    path(
        "projects/<int:design_id>/duplicate/",
        views.duplicate_solar_design,
        name="duplicate_design",
    ),

    path(
        "projects/<int:design_id>/archive/",
        views.archive_design,
        name="archive_design",
    ),

    path(
        "projects/<int:design_id>/restore/",
        views.restore_design,
        name="restore_design",
    ),

    path(
        "projects/<int:design_id>/delete/",
        views.delete_solar_design,
        name="delete_design",
    ),

    path(
        "archived/",
        views.archived_projects,
        name="archived_projects",
    ),


    # ==============================================================
    # VERSION CONTROL
    # ==============================================================

    path(
        "projects/<int:design_id>/versions/",
        views.project_versions,
        name="project_versions",
    ),

    path(
        "projects/<int:design_id>/versions/save/",
        views.save_project_version,
        name="save_project_version",
    ),

    path(
        "versions/<int:version_id>/restore/",
        views.restore_project_version,
        name="restore_project_version",
    ),



    path("webhooks/paystack/", paystack_webhook, name="paystack_webhook"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

