# Generated by Django 2.2.13 on 2021-01-19 11:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_auto_20200303_1657'),
    ]

    operations = [
        migrations.AddField(
            model_name='coreuser',
            name='avatar',
            field=models.ImageField(blank=True, null=True, upload_to='', verbose_name='User avatar'),
        ),
    ]
