# apps/properties/migrations/0002_prepare_project_schema.py

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0001_initial'),
    ]

    operations = [
        # 1. Yeni Project modelini oluşturur
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True, verbose_name='Proje Adı')),
                ('location', models.CharField(blank=True, max_length=255, verbose_name='Konum')),
                ('description', models.TextField(blank=True, verbose_name='Açıklama')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Oluşturulma Tarihi')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Güncellenme Tarihi')),
            ],
            options={
                'verbose_name': 'Proje',
                'verbose_name_plural': 'Projeler',
                'ordering': ['name'],
            },
        ),
        # 2. Eski unique kısıtlamasını kaldırır
        migrations.AlterUniqueTogether(
            name='property',
            unique_together=set(),
        ),
        # 3. Yeni 'project' alanını boş bırakılabilir (nullable) olarak ekler
        migrations.AddField(
            model_name='property',
            name='project',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='properties', to='properties.project', verbose_name='Proje'),
        ),
    ]
