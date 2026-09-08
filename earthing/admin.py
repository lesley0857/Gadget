from django.contrib import admin
from .models import FieldEarthingDesign
@admin.register(FieldEarthingDesign)
class FieldEarthingDesignAdmin(admin.ModelAdmin):
 list_display=("project_name","installation_type","user","created_at"); readonly_fields=("inputs","result","created_at")
