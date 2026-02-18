import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DI4D_app', '0010_fileshare_canedit'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fileshare',
            name='userId',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='shared_file_items', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='fileshare',
            name='userTypeId',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='shared_file_items_by_type', to='DI4D_app.usertype'),
        ),
    ]
