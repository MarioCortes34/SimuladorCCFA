from django.core.management.base import BaseCommand
from simulador.models import Pregunta

PREGUNTAS_AUDIT = [
    {
        "numero": 9001,
        "enunciado": "¿Por cuánto tiempo retiene CrowdStrike Falcon los logs de RTR (Real Time Response)?",
        "opciones": ["A. 30 días", "B. 90 días", "C. 180 días", "D. 365 días"],
        "respuesta_correcta": "B. 90 días",
        "explicacion": "Los logs de RTR se retienen únicamente 90 días, a diferencia de otros logs como Falcon UI o Prevention Policy que se guardan 365 días.",
        "categoria": "Audit Logs & Compliance",
    },
    {
        "numero": 9002,
        "enunciado": "¿Cuánto tiempo retienen los logs de Falcon UI, API Audit y Prevention Policy?",
        "opciones": ["A. 90 días", "B. 180 días", "C. 365 días", "D. 730 días"],
        "respuesta_correcta": "C. 365 días",
        "explicacion": "Falcon UI, API Audit Log y Prevention Policy conservan logs durante 365 días (1 año), frente a los 90 días de RTR.",
        "categoria": "Audit Logs & Compliance",
    },
    {
        "numero": 9003,
        "enunciado": "¿Cuántas entradas puede mostrar simultáneamente la mayoría de tablas en el Falcon Console?",
        "opciones": ["A. 1,000", "B. 5,000", "C. 10,000", "D. 50,000"],
        "respuesta_correcta": "C. 10,000",
        "explicacion": "La mayoría de tablas en el Falcon Console tienen una capacidad máxima de visualización de 10,000 entradas a la vez.",
        "categoria": "Audit Logs & Compliance",
    },
    {
        "numero": 9004,
        "enunciado": "¿Qué log de auditoría utilizarías para monitorear ejecuciones en rutas excluidas de sensores?",
        "opciones": ["A. API Audit Log", "B. Sensor Visibility Exclusions", "C. RTR Audit Log", "D. Prevention Policy Debug"],
        "respuesta_correcta": "B. Sensor Visibility Exclusions",
        "explicacion": "El log Sensor Visibility Exclusions permite ver qué procesos se ejecutaron en rutas excluidas del sensor.",
        "categoria": "Audit Logs & Compliance",
    },
    {
        "numero": 9005,
        "enunciado": "¿Qué ocurre con la actividad maliciosa en rutas configuradas como Sensor Visibility Exclusions?",
        "opciones": [
            "A. Se detecta pero no se previene",
            "B. Se registra automáticamente en el API Audit Log",
            "C. NO es detectada ni prevenida",
            "D. Se envía una alerta al SIEM configurado",
        ],
        "respuesta_correcta": "C. NO es detectada ni prevenida",
        "explicacion": "Este es un punto crítico de seguridad: la actividad maliciosa en rutas excluidas NO será detectada ni prevenida por el sensor de Falcon.",
        "categoria": "Audit Logs & Compliance",
    },
    {
        "numero": 9006,
        "enunciado": "¿Qué identificador utiliza el Prevention Policy Debug log para el troubleshooting individual de un endpoint?",
        "opciones": ["A. CID (Customer ID)", "B. AID (Agent ID)", "C. UUID del sensor", "D. Hostname del endpoint"],
        "respuesta_correcta": "B. AID (Agent ID)",
        "explicacion": "El Prevention Policy Debug usa el AID (Agent ID) para identificar un sensor específico y comparar su configuración activa con la política desplegada.",
        "categoria": "Audit Logs & Compliance",
    },
    {
        "numero": 9007,
        "enunciado": "¿Qué compara el Prevention Policy Debug log para diagnosticar problemas de configuración?",
        "opciones": [
            "A. Los logs de RTR con los de UI",
            "B. El 'Sensor Heartbeat' con los settings desplegados",
            "C. Las exclusiones con las detecciones activas",
            "D. El CID del tenant con el AID del agente",
        ],
        "respuesta_correcta": "B. El 'Sensor Heartbeat' con los settings desplegados",
        "explicacion": "El Prevention Policy Debug compara el Sensor Heartbeat (lo que el sensor reporta) con los settings desplegados (lo que la política dice), revelando discrepancias.",
        "categoria": "Audit Logs & Compliance",
    },
    {
        "numero": 9008,
        "enunciado": "¿Qué niveles de sensibilidad evalúa el ML Prevention Monitoring?",
        "opciones": [
            "A. Low, Medium, High, Critical",
            "B. Cautious, Moderate, Aggressive, Extra Aggressive",
            "C. Basic, Standard, Advanced, Expert",
            "D. Tier 1, Tier 2, Tier 3, Tier 4",
        ],
        "respuesta_correcta": "B. Cautious, Moderate, Aggressive, Extra Aggressive",
        "explicacion": "ML Prevention Monitoring evalúa cuatro niveles: Cautious, Moderate, Aggressive y Extra Aggressive, comparando cuánto malware potencial bloquearía cada nivel.",
        "categoria": "Audit Logs & Compliance",
    },
    {
        "numero": 9009,
        "enunciado": "¿Qué tipo de cambios registra exclusivamente el API Audit Log de CrowdStrike?",
        "opciones": [
            "A. Todos los cambios en la UI y la API",
            "B. Solo cambios realizados vía OAuth2 APIs",
            "C. Solo cambios en políticas de prevención",
            "D. Cambios en exclusiones de visibilidad del sensor",
        ],
        "respuesta_correcta": "B. Solo cambios realizados vía OAuth2 APIs",
        "explicacion": "El API Audit Log registra ÚNICAMENTE los cambios realizados vía OAuth2 APIs. Los cambios hechos directamente en la Falcon Console UI NO aparecen aquí.",
        "categoria": "Audit Logs & Compliance",
    },
    {
        "numero": 9010,
        "enunciado": "Un administrador modifica una política directamente en la Falcon Console UI. ¿En qué log aparecerá ese cambio?",
        "opciones": [
            "A. API Audit Log",
            "B. UI Audit Log (Falcon Console Audit Log)",
            "C. Prevention Policy Debug",
            "D. RTR Audit Log",
        ],
        "respuesta_correcta": "B. UI Audit Log (Falcon Console Audit Log)",
        "explicacion": "El API Audit Log NO registra cambios de UI. Los cambios hechos en la Falcon Console UI quedan registrados en el UI Audit Log.",
        "categoria": "Audit Logs & Compliance",
    },
    {
        "numero": 9011,
        "enunciado": "¿Para qué se utiliza principalmente el ML Prevention Monitoring log?",
        "opciones": [
            "A. Para ver qué IPs bloqueó el firewall perimetral",
            "B. Para evaluar niveles de sensibilidad comparando malware potencial bloqueado",
            "C. Para auditar cambios de políticas realizados vía API",
            "D. Para monitorear la duración de sesiones RTR activas",
        ],
        "respuesta_correcta": "B. Para evaluar niveles de sensibilidad comparando malware potencial bloqueado",
        "explicacion": "ML Prevention Monitoring ayuda a los administradores a elegir el nivel de agresividad del ML mostrando cuánto malware potencial habría bloqueado cada nivel.",
        "categoria": "Audit Logs & Compliance",
    },
    {
        "numero": 9012,
        "enunciado": "Un analista investiga por qué un sensor no aplica correctamente su política de prevención. ¿Qué log debe consultar?",
        "opciones": [
            "A. API Audit Log",
            "B. RTR Audit Log",
            "C. Prevention Policy Debug",
            "D. Sensor Visibility Exclusions",
        ],
        "respuesta_correcta": "C. Prevention Policy Debug",
        "explicacion": "Prevention Policy Debug está diseñado exactamente para este caso: permite comparar la política desplegada con lo que el sensor reporta en su heartbeat, identificando discrepancias.",
        "categoria": "Audit Logs & Compliance",
    },
    {
        "numero": 9013,
        "enunciado": "¿Cuál es la limitación principal al exportar logs desde el Falcon Console?",
        "opciones": [
            "A. Solo se pueden exportar los últimos 30 días",
            "B. No se puede exportar todo el log a la vez; solo los resultados de la búsqueda filtrada",
            "C. El formato de exportación es únicamente XML",
            "D. El máximo es 100 registros por exportación",
        ],
        "respuesta_correcta": "B. No se puede exportar todo el log a la vez; solo los resultados de la búsqueda filtrada",
        "explicacion": "Falcon no permite exportar el log completo en una sola operación. Solo se pueden exportar los resultados de la búsqueda o filtro activo en ese momento.",
        "categoria": "Audit Logs & Compliance",
    },
    {
        "numero": 9014,
        "enunciado": "¿Qué protocolo de autenticación utilizan las APIs cuyas acciones quedan registradas en el API Audit Log?",
        "opciones": ["A. SAML 2.0", "B. Basic Authentication", "C. OAuth2", "D. API Key estática"],
        "respuesta_correcta": "C. OAuth2",
        "explicacion": "El API Audit Log de CrowdStrike registra exclusivamente las acciones realizadas a través de OAuth2 APIs, el estándar de autenticación de la plataforma Falcon.",
        "categoria": "Audit Logs & Compliance",
    },
    {
        "numero": 9015,
        "enunciado": "¿Cuántos días más retienen los logs de Falcon UI comparados con los logs de RTR?",
        "opciones": ["A. 90 días más", "B. 180 días más", "C. 275 días más", "D. 365 días más"],
        "respuesta_correcta": "C. 275 días más",
        "explicacion": "Falcon UI retiene 365 días y RTR solo 90 días. La diferencia es 365 - 90 = 275 días.",
        "categoria": "Audit Logs & Compliance",
    },
    {
        "numero": 9016,
        "enunciado": "¿Qué riesgo de seguridad implica añadir una ruta crítica al Sensor Visibility Exclusions?",
        "opciones": [
            "A. Aumenta el consumo de CPU del sensor en esa ruta",
            "B. La actividad maliciosa en esa ruta no será detectada ni prevenida por Falcon",
            "C. El sensor deja de enviar heartbeats desde ese endpoint",
            "D. Las políticas de ML dejan de aplicarse globalmente",
        ],
        "respuesta_correcta": "B. La actividad maliciosa en esa ruta no será detectada ni prevenida por Falcon",
        "explicacion": "Añadir rutas sensibles a Sensor Visibility Exclusions crea un punto ciego de seguridad: cualquier malware que opere en esa ruta quedará invisible para Falcon.",
        "categoria": "Audit Logs & Compliance",
    },
    {
        "numero": 9017,
        "enunciado": "Un equipo de seguridad quiere auditar todas las integraciones automatizadas que modificaron políticas en el último mes. ¿Qué log consultan?",
        "opciones": [
            "A. UI Audit Log",
            "B. RTR Audit Log",
            "C. API Audit Log",
            "D. Prevention Policy Debug",
        ],
        "respuesta_correcta": "C. API Audit Log",
        "explicacion": "Las integraciones automatizadas usan OAuth2 APIs, por lo que sus cambios quedan registrados en el API Audit Log, no en el UI Audit Log.",
        "categoria": "Audit Logs & Compliance",
    },
    {
        "numero": 9018,
        "enunciado": "¿Qué afirmación sobre el API Audit Log es INCORRECTA?",
        "opciones": [
            "A. Registra cambios realizados mediante OAuth2",
            "B. Retiene los datos durante 365 días",
            "C. Incluye los cambios realizados manualmente en la Falcon Console UI",
            "D. Es útil para auditar integraciones SOAR y scripts automatizados",
        ],
        "respuesta_correcta": "C. Incluye los cambios realizados manualmente en la Falcon Console UI",
        "explicacion": "Esta afirmación es FALSA. El API Audit Log NO incluye los cambios de la UI. Es uno de los puntos más importantes del examen CCFA.",
        "categoria": "Audit Logs & Compliance",
    },
]


class Command(BaseCommand):
    help = "Agrega las preguntas de Audit Logs & Compliance al simulador"

    def handle(self, *args, **options):
        creadas = 0
        for datos in PREGUNTAS_AUDIT:
            _, created = Pregunta.objects.update_or_create(
                numero=datos["numero"],
                defaults={k: v for k, v in datos.items() if k != "numero"},
            )
            if created:
                creadas += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{creadas} preguntas nuevas agregadas ({len(PREGUNTAS_AUDIT)} procesadas)."
            )
        )
