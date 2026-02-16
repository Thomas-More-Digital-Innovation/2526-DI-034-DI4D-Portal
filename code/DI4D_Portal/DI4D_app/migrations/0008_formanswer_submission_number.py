from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DI4D_app', '0006_question_content_alter_formanswer_userid'),
    ]

    operations = [
        migrations.AddField(
            model_name='formanswer',
            name='submission_number',
            field=models.IntegerField(null=True, blank=True),
        ),
    ]
