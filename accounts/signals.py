from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from cart.models import Cart, CartItem
from catalog.models import ProductListing

from django.db.models.signals import post_save
from django.contrib.auth.models import User
from .models import UserProfile


@receiver(user_logged_in)
def merge_cart(sender, request, user, **kwargs):
    session_cart = request.session.get('cart', {})

    cart, _ = Cart.objects.get_or_create(user=user)

    for listing_id, data in session_cart.items():
        listing = ProductListing.objects.get(id=listing_id)

        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product_listing=listing
        )

        if not created:
            item.quantity += data['quantity']
        else:
            item.quantity = data['quantity']

        item.save()

    request.session['cart'] = {}



def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

post_save.connect(create_user_profile, sender=User)