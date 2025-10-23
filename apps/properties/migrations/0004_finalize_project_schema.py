# apps/properties/migrations/0004_finalize_project_schema.py

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0003_migrate_project_data'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='property',
            name='project_name',
        ),
        migrations.AlterField(
            model_name='property',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='properties', to='properties.project', verbose_name='Proje'),
        ),
        migrations.AlterUniqueTogether(
            name='property',
            unique_together={('project', 'block', 'floor', 'unit_number')},
        ),
    ]
