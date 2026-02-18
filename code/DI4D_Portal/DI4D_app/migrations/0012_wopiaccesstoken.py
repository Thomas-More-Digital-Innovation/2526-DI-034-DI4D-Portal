import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DI4D_app', '0011_fileshare_usertype_share'),
    ]

    operations = [
        migrations.CreateModel(
            name='WopiAccessToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tokenHash', models.CharField(max_length=64, unique=True)),
                ('canEdit', models.BooleanField(default=False)),
                ('expiresAt', models.DateTimeField()),
                ('isRevoked', models.BooleanField(default=False)),
                ('createdAt', models.DateTimeField(auto_now_add=True)),
                ('fileItemId', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='wopi_tokens', to='DI4D_app.fileitem')),
                ('userId', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='wopi_tokens', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
