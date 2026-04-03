from django.shortcuts import render

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

    return render(request, 'accounts/login.html')

def logout_view(request):
    logout(request)
    return redirect('home')


def home(request):
    productList = ProductListing.objects.all()  # Featured products
    return render(request, 'base.html', {'productList': productList})

def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    return render(request, 'product_detail.html', {'product': product})

@login_required
def profile(request):
    orders = OrderItem.objects.filter(order__customer=request.user)

    return render(request, "profile.html", {
        "orders": orders
    })

class VendorProfileView(generics.RetrieveAPIView):
    serializer_class = VendorSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return Vendor.objects.get(user=self.request.user)


@login_required
def vendor_dashboard(request):
    vendor = request.user.vendor

    items = OrderItem.objects.filter(vendor=vendor)
    wallet, _ = VendorWallet.objects.get_or_create(vendor=vendor)

    return render(request, "vendorDashboard.html", {
        "items": items,
        "wallet": wallet
    })

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