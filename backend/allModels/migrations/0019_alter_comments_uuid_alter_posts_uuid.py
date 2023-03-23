# Generated by Django 4.1.6 on 2023-03-23 10:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('allModels', '0018_alter_comments_uuid_alter_inbox_likes_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='comments',
            name='uuid',
            field=models.CharField(default='a843dd60-6eae-425d-bf63-25f38a438184', max_length=255, unique=True),
        ),
        migrations.AlterField(
            model_name='posts',
            name='uuid',
            field=models.CharField(default='0d223b79-6c00-4e7d-a880-02103e3ea5cd', max_length=255, unique=True),
        ),
    ]
