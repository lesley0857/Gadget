import random
from django.shortcuts import render,redirect
from django.core.paginator import Paginator

# Create your views here.
from rest_framework import generics, permissions
from .models import Vendor
from catalog.models import *
from .serializers import VendorSerializer
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404,redirect

from django.contrib.auth import authenticate, login, logout
from .models import *
from wallets.models import *
from orders.models import *
from withdrawals.views import *
from services.models import *
from blog.models import *

def custom_404(request, exception):
    return render(request, "404.html", status=404)

def register_view(request):
    if request.user.is_authenticated:
            return redirect("home")
    if request.method == "POST":
        email = request.POST['email']
        username = request.POST['username']
        password = request.POST['password']

        # ✅ CHECK IF EMAIL EXISTS
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return redirect('account_signup')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect('account_signup')
        
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        return redirect('account_login')

    return render(request, 'account/signup.html')

def login_view(request):
    if request.user.is_authenticated:
            return redirect("home")
    if request.method == "POST":
        email = request.POST['email']
        password = request.POST['password']

        user = authenticate(request, username=email, password=password)

        if user:
            login(request, user)
            return redirect('home')

    return render(request, 'account/login.html')


def logout_view(request):
    logout(request)
    return redirect('home')

def about_us(request):
    context = {"services": Service.objects.filter(is_active=True)}
    return render(request,"about-us.html",context)

def privacy_policy(request):
    return render(request, "privacy_policy.html")


def terms_and_conditions(request):
    return render(request, "terms_and_conditions.html")


def home(request):
    productList = ProductListing.objects.filter(
        is_active=True
    ).order_by("-created_at") # Featured productList
    
    paginator = Paginator(productList, 20)
    page_number = request.GET.get("page")
    productList = paginator.get_page(
        page_number
    )
    random.shuffle(list(productList))
    services = Service.objects.filter(is_active=True)
    blogs=BlogPost.objects.all()
    second_categories = Category.objects.filter(
        parent=None
    )[:6]

    products_for_second_categories = ProductListing.objects.filter(
        is_active=True
    )[:24]

    featured_products = ProductListing.objects.filter(
        is_featured=True
    )[:24]

    new_products = ProductListing.objects.filter(
    is_active=True).order_by("-created_at")[:10]

    trending_products = ProductListing.objects.filter(
        is_active=True).order_by("-units_sold")[:15]
 
    if request.method == "POST":

        ServiceRFQ.objects.create(
            service = Service.objects.filter().first(),
            name=request.POST.get("name"),
            email=request.POST.get("email"),

            phone=request.POST.get("phone"),

            company=request.POST.get("company"),

            message=request.POST.get("message"),

            document=request.FILES.get("document")
        )

        messages.success(
            request,
            "Your quotation request has been submitted successfully."
        )

        return redirect(
            "home",
        )
    

    return render(request, 'base.html', 
                  {'productList': productList,
                "categories": Category.objects.all(),
                "services":services,
                "blogs":blogs,
                "second_categories":second_categories,
                "products_for_second_categories":products_for_second_categories,
                "featured_products":featured_products,
                "trending_products":trending_products,
                "new_products":new_products,
                })

def product_detail(request, name):
    product_listing = get_object_or_404(
        ProductListing,
        name=name
    )
    media_items = product_listing.media.order_by(
        "-is_primary", "sort_order", "id"
    )
    related_products = ProductListing.objects.filter(
        categories__in = product_listing.categories.all(),
        is_active=True
    ).exclude(
                id=product_listing.id
             ).distinct()[:12]

    return render(
        request,
        "product_detail.html",
        {
            "product_listing": product_listing,
            "related_products": related_products,
            "media_items": media_items,
            "primary_media": media_items.first(),
        }
    )


@login_required
def profile_view(request):
    profile = UserProfile.objects.filter(user=request.user).first()

    # =========================
    # ORDERS
    # =========================

    orders = Order.objects.filter(
        customer=request.user
    )

    total_orders = orders.count()

    active_orders = orders.filter(
        status__in=["pending", "processing", "paid"]
    ).count()

    completed_orders = OrderItem.objects.filter(
        order__customer=request.user,
        status="delivered"
    ).values(
        "order"
    ).distinct().count()

    # =========================
    # TOTAL SPENT
    # =========================

    total_spent = sum(
        order.total_amount
        for order in orders.filter(status="paid")
    )

    # =========================
    # RECENT ORDERS
    # =========================

    recent_orders = orders.order_by(
        "-created_at"
    )[:5]

    context = {

        "profile": profile,

        "total_orders": total_orders,

        "active_orders": active_orders,

        "completed_orders": completed_orders,

        "total_spent": total_spent,

        "recent_orders": recent_orders,
    }
    return render(request, "account/profile.html", context=context)


@login_required
def update_profile(request):
    profile, created = UserProfile.objects.get_or_create(
    user=request.user
    )

    if request.method == "POST":
        profile.first_name = request.POST.get("first_name")
        profile.last_name = request.POST.get("last_name")
        profile.phone = request.POST.get("phone")
        profile.address = request.POST.get("address")
        profile.city = request.POST.get("city")
        profile.state = request.POST.get("state")
        profile.latitude = request.POST.get("latitude")
        profile.longitude = request.POST.get("longitude")
        if request.FILES.get("image"):
            profile.image = request.FILES["image"]
        profile.save()

        return redirect("profile")

    return render(request, "account/update_profile.html", {"profile": profile})

class VendorProfileView(generics.RetrieveAPIView):
    serializer_class = VendorSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return Vendor.objects.get(user=self.request.user)


def vendor_signup(request):
    if not request.user.is_authenticated:
        messages.info(request, "Please log in or register before becoming a vendor.")
        return redirect("account_login")

    # Already a vendor → go to dashboard
    if hasattr(request.user, "vendor"):
        return redirect("vendor_dashboard")

    NIGERIAN_STATES = [
        "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa",
        "Benue", "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti",
        "Enugu", "FCT", "Gombe", "Imo", "Jigawa", "Kaduna", "Kano",
        "Katsina", "Kebbi", "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger",
        "Ogun", "Ondo", "Osun", "Oyo", "Plateau", "Rivers", "Sokoto",
        "Taraba", "Yobe", "Zamfara",
    ]

    if request.method == "POST":
        store_name = request.POST.get("store_name", "").strip()
        phone = request.POST.get("phone", "").strip()
        description = request.POST.get("description", "").strip()
        address = request.POST.get("address", "").strip()
        city = request.POST.get("city", "").strip()
        state_name = request.POST.get("state", "").strip()
        logo = request.FILES.get("logo")

        errors = []
        if not store_name:
            errors.append("Store name is required.")
        if not phone:
            errors.append("Phone number is required.")
        if not address:
            errors.append("Business address is required.")
        if not city:
            errors.append("City is required.")
        if not state_name:
            errors.append("State is required.")

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, "vendor_signup.html", {
                "post": request.POST,
                "nigerian_states": NIGERIAN_STATES,
            })

        # Auto-geocode from city / state
        from logistics.utils import geocode_address
        lat, lon = geocode_address(address, city, state_name)
        coordinates_pending = lat is None

        # Resolve or create State FK
        from locations.models import State as StateModel
        state_obj = StateModel.objects.filter(name__iexact=state_name).first()

        vendor = Vendor.objects.create(
            user=request.user,
            store_name=store_name,
            phone=phone,
            description=description,
            address=f"{address}, {city}, {state_name}",
            state=state_obj,
            latitude=str(lat) if lat else "",
            longitude=str(lon) if lon else "",
            coordinates_pending=coordinates_pending,
            verified=False,
        )

        if logo:
            vendor.logo = logo
            vendor.save(update_fields=["logo"])

        request.user.is_vendor = True
        request.user.save(update_fields=["is_vendor"])

        # Notify Admin of new vendor application
        from django.core.mail import send_mail
        from django.conf import settings
        try:
            send_mail(
                subject=f"New Vendor Application: {store_name}",
                message=(
                    f"A new vendor application has been submitted by {request.user.email} for store '{store_name}'.\n\n"
                    f"Phone: {phone}\n"
                    f"Address: {address}, {city}, {state_name}\n\n"
                    f"Please review and verify this application in the Django Admin portal."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[getattr(settings, "ADMIN_EMAIL", "nwekelesley@gmail.com")],
                fail_silently=True,
            )
        except Exception as e:
            print("Error notifying admin of vendor application:", e)

        messages.info(
            request,
            f"Your vendor application for '{store_name}' has been submitted! Our Admin team will review and verify your account shortly."
        )
        return redirect("vendor_dashboard")

    return render(request, "vendor_signup.html", {
        "nigerian_states": NIGERIAN_STATES,
    })

@login_required
def vendor_dashboard(request):
    if not hasattr(request.user, "vendor"):
        messages.warning(request, "You don't have a vendor account yet.")
        return redirect("vendor_signup")

    vendor = request.user.vendor

    if not vendor.verified:
        return render(request, "vendor_pending.html", {"vendor": vendor})
    items = OrderItem.objects.filter(
        vendor=vendor
    ).select_related(
        "order", "product_listing"
    ).order_by("-order__created_at")

    wallet, _ = VendorWallet.objects.get_or_create(vendor=vendor)

    from django.db.models import Sum
    agg = items.aggregate(
        total_sales=Sum("total"),
        total_orders=Sum("quantity"),
    )
    total_sales = agg["total_sales"] or 0
    total_orders = items.count()
    pending_items = items.filter(status="pending").count()

    products = ProductListing.objects.filter(
        vendor=vendor,
        is_active=True,
    ).order_by("-created_at")[:10]

    return render(request, "vendor_dashboard.html", {
        "vendor": vendor,
        "items": items[:20],
        "total_sales": total_sales,
        "total_orders": total_orders,
        "pending_items": pending_items,
        "wallet": wallet,
        "products": products,
    })


@login_required
def vendor_update(request):
    if not hasattr(request.user, "vendor"):
        return redirect("vendor_signup")

    vendor = request.user.vendor

    NIGERIAN_STATES = [
        "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa",
        "Benue", "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti",
        "Enugu", "FCT", "Gombe", "Imo", "Jigawa", "Kaduna", "Kano",
        "Katsina", "Kebbi", "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger",
        "Ogun", "Ondo", "Osun", "Oyo", "Plateau", "Rivers", "Sokoto",
        "Taraba", "Yobe", "Zamfara",
    ]

    if request.method == "POST":
        vendor.store_name = request.POST.get("store_name", vendor.store_name).strip()
        vendor.phone = request.POST.get("phone", vendor.phone or "").strip()
        vendor.description = request.POST.get("description", "").strip()

        city = request.POST.get("city", "").strip()
        state_name = request.POST.get("state", "").strip()
        address = request.POST.get("address", "").strip()

        if address or city or state_name:
            vendor.address = f"{address}, {city}, {state_name}".strip(", ")

            from logistics.utils import geocode_address
            lat, lon = geocode_address(address, city, state_name)
            if lat:
                vendor.latitude = str(lat)
                vendor.longitude = str(lon)
                vendor.coordinates_pending = False
            else:
                vendor.coordinates_pending = True

            from locations.models import State as StateModel
            state_obj = StateModel.objects.filter(name__iexact=state_name).first()
            if state_obj:
                vendor.state = state_obj

        if request.FILES.get("logo"):
            vendor.logo = request.FILES["logo"]

        vendor.save()
        messages.success(request, "Store profile updated successfully.")
        return redirect("vendor_dashboard")

    return render(request, "vendor_update.html", {
        "vendor": vendor,
        "nigerian_states": NIGERIAN_STATES,
    })

def vendor_delete(request):
    vendor = request.user.vendor

    if request.method == "POST":
        vendor.delete()
        request.user.is_vendor = False
        request.user.save()
        return redirect("home")

    return render(request, "vendor_delete.html")

def mark_shipped(request, item_id):
    item = OrderItem.objects.get(id=item_id)

    if request.user.vendor == item.vendor:
        item.status = "shipped"
        item.save()

    return redirect("vendor_dashboard")

def vendor_store(request, vendor_id):
    vendor = Vendor.objects.get(id=vendor_id)
    products = ProductListing.objects.filter(vendor=vendor)

    return render(request, "vendor_store.html", {
        "vendor": vendor,
        "products": products
    })

def confirm_delivery(request, item_id):
    item = OrderItem.objects.get(id=item_id)

    item.received = True
    item.status = "delivered"
    item.save()

    release_payment(item)

    return redirect("orders")
