import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('simulador', '0002_pregunta_categoria_progresopregunta'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tenant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=50, unique=True)),
            ],
            options={
                'ordering': ['nombre'],
            },
        ),
        migrations.AddField(
            model_name='progresopregunta',
            name='tenant',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='simulador.tenant'),
        ),
        migrations.AddField(
            model_name='progresopregunta',
            name='racha_correcta',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='progresopregunta',
            name='session_key',
            field=models.CharField(blank=True, db_index=True, default='', max_length=40),
        ),
        migrations.AlterUniqueTogether(
            name='progresopregunta',
            unique_together=set(),
        ),
    ]
