
# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from .models import Cart, CartItem
from catalog.models import ProductListing
from django.http import JsonResponse
from django.views.decorators.http import require_POST



def add_to_cart(request, listing_id):
    if request.method == "POST":
        listing = get_object_or_404(ProductListing, id=listing_id)

        cart_items_data = []
        total = 0

        # ✅ AUTHENTICATED USER
        if request.user.is_authenticated:
            cart, _ = Cart.objects.get_or_create(user=request.user)

            item, created = CartItem.objects.get_or_create(
                cart=cart,
                product_listing=listing
            )

            if not created:
                item.quantity += 1
                item.save()

            items = cart.items.all()

            for i in items:
                price = i.product_listing.calculate_price()
                subtotal = price * i.quantity

                cart_items_data.append({
                    "id": i.product_listing.id,
                    "name": i.product_listing.product.name,
                    "price": float(price),
                    "quantity": i.quantity,
                    "subtotal": float(subtotal),
                    "image": i.product_listing.media.filter(is_primary=True).first().file.url if i.product_listing.media.filter(is_primary=True).exists() else ""
                })

                total += subtotal

        # ✅ ANONYMOUS USER (SESSION CART)
        else:
            cart = request.session.get('cart', {})

            if str(listing_id) in cart:
                cart[str(listing_id)]['quantity'] += 1
            else:
                cart[str(listing_id)] = {'quantity': 1}

            request.session['cart'] = cart

            for id, item in cart.items():
                p = ProductListing.objects.get(id=id)

                price = p.calculate_price()
                quantity = item['quantity']
                subtotal = price * quantity

                cart_items_data.append({
                    "id": i.product_listing.id,
                    "name": i.product_listing.product.name,
                    "price": float(price),
                    "quantity": i.quantity,
                    "subtotal": float(subtotal),
                    "image": i.product_listing.media.filter(is_primary=True).first().file.url if i.product_listing.media.filter(is_primary=True).exists() else ""
                })

                total += subtotal

        return JsonResponse({
            "success": True,
            "cart_items": cart_items_data,
            "total": float(total),
            "cart_count": sum(i["quantity"] for i in cart_items_data)
        })

    return JsonResponse({"success": False}, status=400)

def remove_from_cart(request, listing_id):
    if request.user.is_authenticated:
        cart = Cart.objects.get(user=request.user)
        CartItem.objects.filter(cart=cart, product_listing_id=listing_id).delete()

    else:
        cart = request.session.get('cart', {})

        if str(listing_id) in cart:
            del cart[str(listing_id)]

        request.session['cart'] = cart

    return redirect('cart')

def cart_view(request):
    items = []
    total = 0

    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)

        for item in cart.items.all():
            items.append({
                'listing': item.product_listing,
                'quantity': item.quantity,
                'total_price': item.get_total_price(),
                'id': item.product_listing.id
            })

            total += item.get_total_price()

    else:
        session_cart = request.session.get('cart', {})

        for listing_id, data in session_cart.items():
            listing = ProductListing.objects.get(id=listing_id)
            quantity = data['quantity']
            total_price = listing.final_price * quantity

            items.append({
                'listing': listing,
                'quantity': quantity,
                'total_price': total_price,
                'id': listing.id
            })

            total += total_price

    return render(request, 'cart.html', {
        'items': items,
        'total': total
    })

@require_POST
def update_cart(request):
    listing_id = request.POST.get("product_id")
    action = request.POST.get("action")

    if request.user.is_authenticated:
        cart = Cart.objects.get(user=request.user)

        try:
            item = CartItem.objects.get(cart=cart, product_listing_id=listing_id)
        except CartItem.DoesNotExist:
            item = None

        if item:
            if action == "increment":
                item.quantity += 1
                item.save()

            elif action == "decrement":
                item.quantity -= 1
                if item.quantity <= 0:
                    item.delete()
                else:
                    item.save()

            elif action == "remove":
                item.delete()

        items = cart.items.all()

    else:
        cart = request.session.get("cart", {})

        if listing_id in cart:
            if action == "increment":
                cart[listing_id]["quantity"] += 1

            elif action == "decrement":
                cart[listing_id]["quantity"] -= 1
                if cart[listing_id]["quantity"] <= 0:
                    del cart[listing_id]

            elif action == "remove":
                del cart[listing_id]

        request.session["cart"] = cart

        items = []
        for id, item in cart.items():
            p = ProductListing.objects.get(id=id)
            items.append({
                "product_listing": p,
                "quantity": item["quantity"]
            })

    # 🔥 ALWAYS REBUILD RESPONSE (NO EARLY RETURN)
    cart_items_data = []
    total = 0

    for i in items:
        if request.user.is_authenticated:
            listing = i.product_listing
            quantity = i.quantity
        else:
            listing = i["product_listing"]
            quantity = i["quantity"]

        price = listing.calculate_price()
        subtotal = price * quantity

        cart_items_data.append({
            "id": listing.id,
            "name": listing.product.name,
            "price": float(price),
            "quantity": quantity,
            "subtotal": float(subtotal),
            "image": listing.media.first().file.url if listing.media.exists() else ""
        })

        total += subtotal

    return JsonResponse({
        "success": True,
        "cart_items": cart_items_data,
        "total": float(total)
    })


from collections import defaultdict
from datetime import timedelta
from django.utils import timezone
from cart.models import CartItem

def checkout_view(request):

    user = request.user
    items = CartItem.objects.filter(cart__user=user)

    vendor_groups = defaultdict(list)

    # GROUP ITEMS BY VENDOR
    for item in items:
        vendor = item.product_listing.vendor
        vendor_groups[vendor].append(item)

    vendors_data = []
    subtotal = 0
    total_shipping = 0

    for vendor, v_items in vendor_groups.items():

        vendor_subtotal = 0

        for item in v_items:
            price = item.product_listing.calculate_price()
            item.unit_price = price
            item.subtotal = price * item.quantity

            vendor_subtotal += item.subtotal

        subtotal += vendor_subtotal

        # 🚚 SHIPPING PER VENDOR
        if user.city and vendor.city and user.city.lower() == vendor.city.lower():
            shipping_fee = 2000
            delivery_days = (1, 2)
            same_city = True
        else:
            shipping_fee = 5000
            delivery_days = (3, 7)
            same_city = False

        total_shipping += shipping_fee

        delivery_start = timezone.now() + timedelta(days=delivery_days[0])
        delivery_end = timezone.now() + timedelta(days=delivery_days[1])

        vendors_data.append({
            "vendor": vendor,
            "items": v_items,
            "vendor_subtotal": vendor_subtotal,
            "shipping_fee": shipping_fee,
            "delivery_start": delivery_start,
            "delivery_end": delivery_end,
            "same_city": same_city
        })

    # 🧾 VAT
    vat = subtotal * int(0.075)

    # 💰 TOTAL
    total = subtotal + total_shipping + vat

    context = {
        "vendors_data": vendors_data,
        "subtotal": subtotal,
        "shipping": total_shipping,
        "vat": vat,
        "total": total,
    }

    return render(request, "checkout.html", context)