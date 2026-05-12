from django.db import models


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
    """Rastrea cuántas veces el usuario vio y acertó cada pregunta (por sesión)."""
    session_key    = models.CharField(max_length=40, db_index=True)
    pregunta       = models.ForeignKey(Pregunta, on_delete=models.CASCADE)
    veces_vista    = models.IntegerField(default=0)
    veces_correcta = models.IntegerField(default=0)

    class Meta:
        unique_together = ['session_key', 'pregunta']

    @property
    def dominada(self):
        return self.veces_vista >= 2 and self.veces_correcta == self.veces_vista
