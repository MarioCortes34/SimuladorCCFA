import json
from pathlib import Path
from django.core.management.base import BaseCommand
from simulador.models import Pregunta


class Command(BaseCommand):
    help = "Importa preguntas desde preguntas_ccfa.json a la base de datos SQLite"

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            default=str(Path.home() / "Desktop" / "SEXO" / "datos" / "preguntas_ccfa.json"),
            help="Ruta al archivo JSON con las preguntas",
        )
        parser.add_argument(
            "--limpiar",
            action="store_true",
            help="Borra todas las preguntas existentes antes de importar",
        )

    def handle(self, *args, **options):
        ruta = Path(options["json"])

        if not ruta.exists():
            self.stderr.write(f"Archivo no encontrado: {ruta}")
            return

        if options["limpiar"]:
            borradas = Pregunta.objects.all().delete()[0]
            self.stdout.write(f"Eliminadas {borradas} preguntas previas.")

        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)

        creadas  = 0
        saltadas = 0

        for idx, item in enumerate(datos, start=1):
            enunciado = item.get("enunciado", "").strip()
            opciones  = item.get("opciones", [])

            # Descarta registros sin texto real
            if not enunciado or enunciado == "Sin enunciado":
                saltadas += 1
                continue

            numero = item.get("numero", idx)
            # Calcula la pagina de origen segun el numero (52 preguntas por pagina aprox)
            pagina = min(5, max(1, ((numero - 1) // 52) + 1))

            if isinstance(opciones, dict):
                opciones = list(opciones.values())

            Pregunta.objects.update_or_create(
                numero=numero,
                defaults={
                    "enunciado":          enunciado,
                    "opciones":           opciones,
                    "respuesta_correcta": item.get("respuesta_correcta", ""),
                    "explicacion":        item.get("explicacion", ""),
                    "pagina":             pagina,
                },
            )
            creadas += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Importacion completada: {creadas} guardadas, {saltadas} descartadas."
            )
        )
