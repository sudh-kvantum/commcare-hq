# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-05-04 06:41
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('icds', '0004_cczhosting_file_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='cczhostinglink',
            name='page_title',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]