from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DI4D_app', '0007_news_content_alter_news_mediapath_alter_news_picture'),
    ]

    operations = [
        migrations.AddField(
            model_name='formanswer',
            name='submission_number',
            field=models.IntegerField(null=True, blank=True),
        ),
    ]
