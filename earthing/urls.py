from django.urls import path
from solar.views import earthing_assessment

urlpatterns = [path("", earthing_assessment, name="earthing_assessment")]
