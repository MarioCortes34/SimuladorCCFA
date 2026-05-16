import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('simulador', '0003_tenant_y_racha'),
    ]

    operations = [
        migrations.CreateModel(
            name='HistorialRespuesta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tiempo_empleado', models.IntegerField(default=0)),
                ('resultado', models.CharField(max_length=20)),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('pregunta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='simulador.pregunta')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='simulador.tenant')),
            ],
            options={
                'ordering': ['-fecha'],
            },
        ),
    ]
