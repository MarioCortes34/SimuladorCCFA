from django.db import models


class Tenant(models.Model):
    nombre = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Pregunta(models.Model):
    numero             = models.IntegerField(unique=True)
    enunciado          = models.TextField()
    opciones           = models.JSONField()
    respuesta_correcta = models.CharField(max_length=500)
    explicacion        = models.TextField(blank=True)
    pagina             = models.IntegerField(default=1)
    categoria          = models.CharField(max_length=120, default='General')

    class Meta:
        ordering = ['numero']

    def __str__(self):
        return f"Q{self.numero}: {self.enunciado[:60]}"


class ProgresoPregunta(models.Model):
    tenant         = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True)
    session_key    = models.CharField(max_length=40, db_index=True, blank=True, default='')
    pregunta       = models.ForeignKey(Pregunta, on_delete=models.CASCADE)
    veces_vista          = models.IntegerField(default=0)
    veces_correcta       = models.IntegerField(default=0)
    racha_correcta       = models.IntegerField(default=0)
    alguna_vez_dominada  = models.BooleanField(default=False)

    class Meta:
        ordering = ['-veces_vista']

    @property
    def dominada(self):
        return self.racha_correcta >= 2

    @property
    def fallida(self):
        return self.veces_vista > 0 and self.veces_correcta < self.veces_vista and not self.dominada

    @property
    def inestable(self):
        # Fue dominada alguna vez pero ya no lo está
        return self.alguna_vez_dominada and not self.dominada


class HistorialRespuesta(models.Model):
    tenant          = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    pregunta        = models.ForeignKey(Pregunta, on_delete=models.CASCADE)
    tiempo_empleado = models.IntegerField(default=0)  # segundos
    resultado       = models.CharField(max_length=20)  # 'Correcto' / 'Incorrecto'
    fecha           = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']
