# Generated by Django 2.1.2 on 2018-12-01 11:40

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('megatron', '0002_auto_20181121_1143'),
    ]

    operations = [
        migrations.AddField(
            model_name='platformuser',
            name='profile_image',
            field=models.CharField(default='', max_length=250),
        ),
    ]
