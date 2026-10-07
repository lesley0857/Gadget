from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0002_alter_blogpost_featured_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="blogpost",
            name="linkedin_post_id",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="blogpost",
            name="linkedin_publish_error",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="blogpost",
            name="linkedin_publish_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
