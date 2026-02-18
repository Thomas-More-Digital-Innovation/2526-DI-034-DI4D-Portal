from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DI4D_app', '0009_fileitem_fileshare'),
    ]

    operations = [
        migrations.AddField(
            model_name='fileshare',
            name='canEdit',
            field=models.BooleanField(default=False),
        ),
    ]
