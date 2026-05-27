from django.shortcuts import render,redirect

# Create your views here.
from rest_framework import generics, permissions
from .models import Vendor
from catalog.models import *
from .serializers import VendorSerializer
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404,redirect
from catalog.models import Product
from django.contrib.auth import authenticate, login, logout
from .models import *
from wallets.models import *
from orders.models import *
from withdrawals.views import *

def custom_404(request, exception):
    return render(request, '404.html', status=404)

def register_view(request):
    if request.method == "POST":
        email = request.POST['email']
        username = request.POST['username']
        password = request.POST['password']

        # ✅ CHECK IF EMAIL EXISTS
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return redirect('register')
        
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        login(request, user)
        return redirect('home')

    return render(request, 'accounts/register.html')

def login_view(request):
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


def home(request):
    productList = ProductListing.objects.all()  # Featured products
    return render(request, 'base.html', {'productList': productList,
                                         "categories": Category.objects.all()})

def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    return render(request, 'product_detail.html', {'product': product})


@login_required
def profile_view(request):

    profile = request.user.userprofile

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
        profile.phone = request.POST.get("phone")
        profile.address = request.POST.get("address")
        profile.city = request.POST.get("city")
        profile.state = request.POST.get("state")
        profile.latitude = request.POST.get("latitude")
        profile.longitude = request.POST.get("longitude")
        profile.save()

        return redirect("profile")

    return render(request, "account/update_profile.html", {"profile": profile})

class VendorProfileView(generics.RetrieveAPIView):
    serializer_class = VendorSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return Vendor.objects.get(user=self.request.user)


def vendor_signup(request):
    if request.method == "POST":
        store_name = request.POST.get("store_name")

        vendor = Vendor.objects.create(
            user=request.user,
            store_name=store_name,
            state=request.user.state
        )

        request.user.is_vendor = True
        request.user.save()

        return redirect("vendor_dashboard")

    return render(request, "vendor_signup.html")

@login_required
def vendor_dashboard(request):
    vendor = request.user.vendor

    items = OrderItem.objects.filter(vendor=vendor)
    wallet, _ = VendorWallet.objects.get_or_create(vendor=vendor)

    total_sales = items.aggregate(total=Sum("total"))["total"] or 0
    total_orders = items.count()

    return render(request, "accounts/vendor_dashboard.html", {
        "items": items,
        "total_sales": total_sales,
        "wallet": wallet,
        "total_orders": total_orders})

def vendor_update(request):
    vendor = request.user.vendor

    if request.method == "POST":
        vendor.store_name = request.POST.get("store_name")
        vendor.save()
        return redirect("vendor_dashboard")

    return render(request, "vendor_update.html", {"vendor": vendor})

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