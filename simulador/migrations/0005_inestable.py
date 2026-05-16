from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('simulador', '0004_historialrespuesta'),
    ]

    operations = [
        migrations.AddField(
            model_name='progresopregunta',
            name='alguna_vez_dominada',
            field=models.BooleanField(default=False),
        ),
    ]
