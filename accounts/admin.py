from django.contrib import admin
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from .models import Vendor, User, UserProfile
from django.contrib.admin import AdminSite

class MyAdminSite(AdminSite):
    login_template = "admin/login.html"

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ["store_name", "user", "phone", "state", "verified", "coordinates_pending"]
    list_filter = ["verified", "coordinates_pending", "state"]
    search_fields = ["store_name", "user__email", "phone"]
    actions = ["approve_vendors", "reject_vendors"]

    @admin.action(description="Approve selected vendors and send approval email")
    def approve_vendors(self, request, queryset):
        count = 0
        for vendor in queryset:
            vendor.verified = True
            vendor.save(update_fields=["verified"])
            count += 1
            if vendor.user and vendor.user.email:
                try:
                    send_mail(
                        subject="Congratulations! Your Remarobe Vendor Account has been Approved",
                        message=(
                            f"Hello {vendor.store_name},\n\n"
                            f"Your vendor account on Remarobe has been officially approved by our admin team!\n"
                            f"You can now access your Vendor Dashboard and start listing electrical and engineering products.\n\n"
                            f"Thank you for joining Remarobe."
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[vendor.user.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    print("Error sending vendor approval email:", e)

        self.message_user(request, f"{count} vendor(s) approved successfully and notified via email.", messages.SUCCESS)

    @admin.action(description="Reject selected vendors and send rejection email")
    def reject_vendors(self, request, queryset):
        count = 0
        for vendor in queryset:
            vendor.verified = False
            vendor.save(update_fields=["verified"])
            count += 1
            if vendor.user and vendor.user.email:
                try:
                    send_mail(
                        subject="Update regarding your Remarobe Vendor Application",
                        message=(
                            f"Hello {vendor.store_name},\n\n"
                            f"We regret to inform you that your vendor application for '{vendor.store_name}' could not be approved at this time.\n"
                            f"Please ensure all required business details and address are provided accurately, then update your store profile to re-submit.\n\n"
                            f"Regards,\nRemarobe Admin Team"
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[vendor.user.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    print("Error sending vendor rejection email:", e)

        self.message_user(request, f"{count} vendor(s) rejected and notified via email.", messages.WARNING)

@admin.register(User)
class UserAdmin(admin.ModelAdmin):

    list_display = (
        "email",
        "username",
        "is_vendor",
        "is_staff"
    )

    search_fields = (
        "email",
        "username"
    )

    list_filter = (
        "is_vendor",
        "is_staff"
    )

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "phone",
        "city",
        "state"
    )

    search_fields = (
        "user__email",
        "phone"
    )
