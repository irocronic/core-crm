# apps/properties/migrations/0003_migrate_project_data.py

from django.db import migrations

def forwards_func(apps, schema_editor):
    Property = apps.get_model('properties', 'Property')
    Project = apps.get_model('properties', 'Project')
    db_alias = schema_editor.connection.alias
    
    project_names = Property.objects.using(db_alias).values_list('project_name', flat=True).distinct()
    
    projects_map = {}
    for name in project_names:
        if name:
            project, created = Project.objects.using(db_alias).get_or_create(name=name)
            projects_map[name] = project

    default_project, _ = Project.objects.using(db_alias).get_or_create(name="Genel Proje")

    for property_instance in Property.objects.using(db_alias).all():
        project = projects_map.get(property_instance.project_name, default_project)
        property_instance.project = project
        property_instance.save(update_fields=['project'])

def reverse_func(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        # Bu, bir önceki (0002) migration dosyamızın adı olmalı
        ('properties', '0002_prepare_project_schema'),
    ]

    operations = [
        migrations.RunPython(forwards_func, reverse_func),
    ]
