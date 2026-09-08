from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("solar", "0016_solardesign_user_optional")]
    operations = [migrations.AddField(model_name="designsetting", name="installation_price", field=models.DecimalField(blank=True, decimal_places=2, help_text="Optional fixed installation charge. When set, this overrides the percentage.", max_digits=14, null=True))]