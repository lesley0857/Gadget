from django.contrib.auth.models import AbstractUser
from django.db import models

from locations.models import *
from django.contrib.auth.models import User
from logistics.models import Hub

class User(AbstractUser):
    is_vendor = models.BooleanField(default=False)
    email = models.EmailField(unique=True)

    state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']


class Vendor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    store_name = models.CharField(max_length=150)
    verified = models.BooleanField(default=False)
    hub = models.ForeignKey(Hub, on_delete=models.SET_NULL, null=True,blank=False )
    state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    latitude = models.CharField(max_length=50, null=True, blank=True)
    longitude = models.CharField(max_length=50, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    
    def __str__(self):
        return self.store_name

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE,related_name='userprofile')

    phone = models.CharField(max_length=20, blank=True, null=True)

    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)

    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    def __str__(self):
        return self.user.username

