from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("solar", "0015_earthingdesign")]
    operations = [migrations.AlterField(model_name="solardesign", name="user", field=models.ForeignKey(blank=True, null=True, on_delete=models.CASCADE, related_name="solar_designs", to="accounts.user"))]
