import re
import time
import random
from django.db.models import Avg, Count, Q
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
from .models import Pregunta, ProgresoPregunta, Tenant, HistorialRespuesta

PASS_SCORE = 45
EXAM_TOTAL = 60
EXAM_MINUTOS = 60
TENANTS_DEFAULT = ['alexander', 'mario']

_tenants_ok = False


def _ensure_tenants():
    global _tenants_ok
    if _tenants_ok:
        return
    for nombre in TENANTS_DEFAULT:
        Tenant.objects.get_or_create(nombre=nombre)
    _tenants_ok = True


def _get_tenant(request):
    _ensure_tenants()
    tid = request.session.get('tenant_id')
    if tid:
        try:
            return Tenant.objects.get(id=tid)
        except Tenant.DoesNotExist:
            pass
    tenant = Tenant.objects.order_by('nombre').first()
    request.session['tenant_id'] = tenant.id
    return tenant


def _letra(texto: str) -> str:
    m = re.match(r'^\s*([A-Da-d])[\.\)\:]\s*', texto.strip())
    if m:
        return m.group(1).upper()
    t = texto.strip()
    if len(t) == 1 and t.isalpha():
        return t.upper()
    return texto.strip().lower()


def _es_correcto(respuesta: str, correcta: str) -> bool:
    return _letra(respuesta) == _letra(correcta)


def _texto_sin_letra(opcion: str) -> str:
    return re.sub(r'^\s*[A-Da-d][\.\)\:]\s*', '', (opcion or '').strip()).strip()


def _barajar_opciones(opciones, respuesta_correcta):
    """Baraja las opciones y reasigna las letras A/B/C/D. Retorna (nuevas_opciones, nueva_letra_correcta)."""
    letras = ['A', 'B', 'C', 'D']
    textos = [_texto_sin_letra(op) for op in opciones]
    correcta_letra = _letra(respuesta_correcta)
    idx_orig = next((i for i, op in enumerate(opciones) if _letra(op) == correcta_letra), 0)
    texto_correcto = textos[idx_orig]
    random.shuffle(textos)
    nuevas_opciones = [f"{l}) {t}" for l, t in zip(letras, textos)]
    nueva_pos = textos.index(texto_correcto)
    nueva_correcta = letras[nueva_pos]
    return nuevas_opciones, nueva_correcta


def _tip_espanol(pregunta, es_correcto: bool) -> str:
    txt = pregunta.enunciado.upper()
    partes = []

    # ── Tipo de pregunta ─────────────────────────────────────────────
    if any(w in txt for w in ['EXCEPT', 'NOT INCLUDE', 'CANNOT', 'DOES NOT', 'NOT TRUE', 'NOT CORRECT', 'WHICH OF THE FOLLOWING IS NOT']):
        partes.append('⚠️ <b>Trampa de negación:</b> Fíjate que la pregunta pide la EXCEPCIÓN. Mentalmente cambia el enunciado a positivo, elige la que NO cumple, y esa es la correcta.')
    if any(w in txt for w in ['BEST', 'MOST LIKELY', 'MOST APPROPRIATE', 'PRIMARY', 'MAIN REASON', 'MAIN PURPOSE', 'MOST IMPORTANT']):
        partes.append('🎯 <b>Pregunta de "la mejor opción":</b> Varias respuestas pueden ser válidas pero solo una es la más directa o más completa. Elimina las que son parcialmente correctas.')
    if any(w in txt for w in ['ONLY', 'ALWAYS', 'NEVER', 'ALL OF THE', 'EVERY', 'MUST']):
        partes.append('⚡ <b>Cuidado con absolutos (ONLY/ALWAYS/NEVER/ALL):</b> Una sola excepción que exista hace que esa opción sea falsa. Si ves "always", desconfía.')
    if any(w in txt for w in ['FIRST', 'INITIAL STEP', 'BEFORE', 'PRIOR TO', 'ORDER', 'SEQUENCE']):
        partes.append('📋 <b>Pregunta de orden:</b> No basta saber que algo es correcto — tienes que saber qué va PRIMERO en el proceso.')
    if any(w in txt for w in ['TWO', 'THREE', 'SELECT TWO', 'SELECT THREE', 'CHOOSE TWO']):
        partes.append('✌️ <b>Respuesta múltiple:</b> Hay más de una respuesta correcta. Analiza cada opción por separado antes de decidir.')

    # ── Conceptos clave CCFA ─────────────────────────────────────────
    if any(w in txt for w in ['AID', 'AGENT ID']):
        partes.append('🔑 <b>AID (Agent ID):</b> Es el identificador ÚNICO de cada sensor instalado en un host. No confundir con CID.')
    if any(w in txt for w in ['CID', 'CUSTOMER ID']):
        partes.append('🔑 <b>CID (Customer ID):</b> Identifica a tu ORGANIZACIÓN en Falcon, no al host individual. El sensor usa el CID para conectarse al cloud correcto.')
    if 'AID' in txt and 'CID' in txt:
        partes.append('🔑 <b>AID vs CID — clave del examen:</b> AID = sensor (el host). CID = cliente (tu empresa). Un CID puede tener miles de AIDs.')
    if any(w in txt for w in ['IOA', 'INDICATOR OF ATTACK']):
        partes.append('🔍 <b>IOA (Indicator of Attack):</b> Detecta comportamiento malicioso EN TIEMPO REAL aunque no haya malware conocido. Clave para fileless attacks y ransomware.')
    if any(w in txt for w in ['IOC', 'INDICATOR OF COMPROMISE', 'HASH', 'CUSTOM IOC']):
        partes.append('🔍 <b>IOC (Indicator of Compromise):</b> Evidencia forense después del ataque — hashes, IPs, dominios. Busca amenazas CONOCIDAS, no comportamientos nuevos.')
    if any(w in txt for w in ['RFM', 'REDUCED FUNCTIONALITY MODE']):
        partes.append('⚙️ <b>RFM (Reduced Functionality Mode):</b> El sensor se activó pero es incompatible con el kernel. Funciona con capacidades limitadas hasta que se actualice el OS o el sensor.')
    if any(w in txt for w in ['RTR', 'REAL TIME RESPONSE', 'REMOTE RESPONSE']):
        partes.append('🖥️ <b>RTR (Real Time Response):</b> Consola remota para ejecutar comandos en hosts en vivo. Sus logs se guardan solo 90 días (los demás logs duran 365 días). Requiere permisos explícitos.')
    if any(w in txt for w in ['SENSOR VISIBILITY EXCLUSION']):
        partes.append('🚫 <b>Sensor Visibility Exclusion:</b> Crea un PUNTO CIEGO total — el sensor ignora completamente esos procesos/rutas. Úsalas con extremo cuidado, solo para herramientas de confianza certificada.')
    if any(w in txt for w in ['ML EXCLUSION', 'MACHINE LEARNING EXCLUSION']):
        partes.append('🚫 <b>ML Exclusion:</b> Solo desactiva la detección por Machine Learning para esa ruta/proceso. El sensor SIGUE monitoreando con IOA y otras capas.')
    if any(w in txt for w in ['IOA EXCLUSION']):
        partes.append('🚫 <b>IOA Exclusion:</b> Suprime las alertas de una regla IOA específica. No desactiva la detección de ML ni de hashes.')
    if any(w in txt for w in ['OVERWATCH', 'OVER WATCH', 'THREAT HUNT']):
        partes.append('👁️ <b>Falcon OverWatch:</b> Equipo HUMANO de CrowdStrike que caza amenazas 24/7. No es automatizado — son analistas reales que intervienen cuando los algoritmos no son suficientes.')
    if any(w in txt for w in ['HOST GROUP', 'HOST GROUPS']):
        partes.append('🗂️ <b>Host Groups:</b> Agrupan hosts para aplicarles políticas específicas. Los grupos se asignan a Prevention Policies y Sensor Update Policies de forma independiente.')
    if any(w in txt for w in ['SENSOR UPDATE', 'UPDATE POLICY', 'UPDATE POLICIES']):
        partes.append('🔄 <b>Sensor Update Policy:</b> Controla QUÉ versión del sensor recibe cada grupo de hosts. Permite canary deployments — primero un grupo pequeño, luego producción.')
    if any(w in txt for w in ['PREVENTION POLICY', 'PREVENTION POLICIES']):
        partes.append('🛡️ <b>Prevention Policy:</b> Define qué detecciones y bloqueos están activos. Cada host solo puede tener UNA prevention policy activa a la vez.')
    if any(w in txt for w in ['FALCON FUSION', 'SOAR', 'WORKFLOW']):
        partes.append('⚡ <b>Falcon Fusion (SOAR):</b> Automatiza respuestas a detecciones mediante workflows. Puede ejecutar acciones sin intervención humana.')
    if any(w in txt for w in ['AUDIT LOG', 'AUDIT TRAIL']):
        partes.append('📋 <b>Audit Logs:</b> Retención de 365 días para logs de UI y API. Los logs de RTR duran solo 90 días. Los de Prevention Policy changes también van al audit log.')
    if any(w in txt for w in ['RBAC', 'ROLE', 'PERMISSION', 'FALCON ROLE']):
        partes.append('🔐 <b>RBAC:</b> Los roles en Falcon son predefinidos (no puedes crear roles custom). Asigna el rol mínimo necesario. Falcon Administrator tiene acceso completo.')
    if any(w in txt for w in ['CONTAINMENT', 'NETWORK CONTAIN', 'CONTAINED']):
        partes.append('🔒 <b>Network Containment:</b> Aísla el host de toda red excepto la comunicación con el Falcon cloud. El sensor sigue funcionando y reportando durante el containment.')
    if any(w in txt for w in ['FALCON COMPLETE', 'MANAGED DETECTION']):
        partes.append('🏢 <b>Falcon Complete:</b> Servicio GESTIONADO — CrowdStrike opera Falcon por ti, incluyendo respuesta a incidentes. No confundir con OverWatch (que solo caza, no opera).')

    # ── Tips de UI y navegación de Falcon ────────────────────────────
    if any(w in txt for w in ['HOST MANAGEMENT', 'HOSTNAME', 'HOST SEARCH', 'HOST FILTER']):
        partes.append('🖥️ <b>Host Management — filtros:</b> En Falcon los filtros de hostname se aplican con lógica OR al agregar el mismo filtro múltiples veces. Un solo campo de hostname busca la cadena LITERAL (coma, espacio, etc. son parte del texto).')
    if any(w in txt for w in ['INVESTIGATE', 'DETECTION', 'ALERT', 'INCIDENT']):
        partes.append('🔎 <b>Investigate:</b> Úsalo para correlacionar detecciones, ver el árbol de procesos y rastrear el origen de un ataque paso a paso.')
    if any(w in txt for w in ['DASHBOARD', 'WIDGET', 'REPORT', 'ACTIVITY APP']):
        partes.append('📊 <b>Dashboards:</b> Los widgets son personalizables por usuario. Los dashboards de Activity App muestran detecciones en tiempo real.')
    if any(w in txt for w in ['NOTIFICATION', 'EMAIL', 'ALERT NOTIFICATION']):
        partes.append('🔔 <b>Notificaciones:</b> Se configuran por severidad y tipo de detección. Requieren que el usuario tenga el rol adecuado para recibirlas.')
    if any(w in txt for w in ['FALCON CONSOLE', 'UI', 'INTERFACE', 'MENU', 'NAVIGATION']):
        partes.append('🖱️ <b>Consola Falcon:</b> Recuerda los menús principales: Activity, Endpoint Security, Investigate, Host Management, Configuration, RBAC.')

    # ── Fallback: si no hay tips contextuales, dar guía de estrategia ─
    if not partes and not pregunta.explicacion:
        partes.append('💡 <b>Sin tip específico:</b> Lee cada opción buscando una palabra que la haga imposible (un absoluto, una negación, o un término técnico incorrecto).')
    elif not partes:
        pass  # Solo aparecerá la explicación del DB

    # ── Explicación del DB — advertir si referencia letras originales ─
    if pregunta.explicacion:
        tiene_ref_letra = bool(re.search(r'(?:correcta|incorrecta|opci[oó]n)\s*\([A-D]\)', pregunta.explicacion, re.IGNORECASE))
        if tiene_ref_letra:
            correcta_texto = _texto_sin_letra(_opcion_por_letra(pregunta, pregunta.respuesta_correcta))
            aviso = (
                f'🔀 <b>Letras barajadas — sin error:</b> Las opciones se reordenan en cada intento. '
                f'La letra que ves en pantalla puede no coincidir con la que menciona la explicación. '
                f'La respuesta correcta siempre es: <span style="color:#86efac;font-weight:700">"{correcta_texto}"</span>'
            )
            partes.insert(0, aviso)
        partes.append(f'📖 <b>Explicación:</b> {pregunta.explicacion}')

    return '<br>'.join(partes) if partes else ''


def _opcion_por_letra(pregunta, respuesta_raw):
    """Devuelve el texto completo de la opción original que coincide con la letra de respuesta_raw."""
    if not respuesta_raw:
        return ''
    letra = _letra(respuesta_raw)
    for op in pregunta.opciones:
        if _letra(op) == letra:
            return op
    return respuesta_raw


def _registrar_progreso(tenant, pregunta, es_correcto):
    obj, _ = ProgresoPregunta.objects.get_or_create(tenant=tenant, pregunta=pregunta)
    obj.veces_vista += 1
    if es_correcto:
        obj.veces_correcta += 1
        obj.racha_correcta += 1
        if obj.racha_correcta >= 2:
            obj.alguna_vez_dominada = True
    else:
        obj.racha_correcta = 0
    obj.save()


def _seleccionar_ponderado(tenant, k):
    todas = list(Pregunta.objects.values_list('id', flat=True))
    progreso_map = {
        p.pregunta_id: p
        for p in ProgresoPregunta.objects.filter(tenant=tenant)
    }
    disponibles = []
    for pid in todas:
        p = progreso_map.get(pid)
        if p is None:
            peso = 3.0
        elif p.dominada:
            peso = 0.2
        elif p.fallida:
            peso = 5.0
        else:
            peso = 2.0
        disponibles.append([pid, peso])

    result = []
    for _ in range(min(k, len(disponibles))):
        total_w = sum(w for _, w in disponibles)
        r = random.uniform(0, total_w)
        acc = 0
        for i, (pid, w) in enumerate(disponibles):
            acc += w
            if acc >= r:
                result.append(pid)
                disponibles.pop(i)
                break
    return result


# ─────────────────────────────────────────────
# Selector de Tenant
# ─────────────────────────────────────────────

def seleccionar_tenant(request):
    _ensure_tenants()
    if request.method == 'POST':
        try:
            request.session['tenant_id'] = int(request.POST.get('tenant_id', 0))
        except (ValueError, TypeError):
            pass
        return redirect('inicio')
    tenants = Tenant.objects.all()
    tenant_actual = _get_tenant(request)
    return render(request, 'simulador/seleccionar_tenant.html', {
        'tenants': tenants,
        'tenant_actual': tenant_actual,
        'tenant': tenant_actual,
    })


# ─────────────────────────────────────────────
# Inicio + Dashboard de Zonas
# ─────────────────────────────────────────────

def inicio(request):
    tenant = _get_tenant(request)
    total = Pregunta.objects.count()
    categorias = (Pregunta.objects.values_list('categoria', flat=True)
                  .distinct().order_by('categoria'))

    # ── Una sola consulta de ProgresoPregunta → reutilizada en todo ──
    progreso_map = {p.pregunta_id: p for p in ProgresoPregunta.objects.filter(tenant=tenant)}
    dominadas    = sum(1 for p in progreso_map.values() if p.dominada)
    fallidas     = sum(1 for p in progreso_map.values() if p.fallida)
    sin_ver_count = total - len(progreso_map)

    # ── Cache de preguntas ────────────────────────────────────────────
    preguntas_cache = {p.pk: p for p in Pregunta.objects.all()}

    # ── Una sola consulta de HistorialRespuesta → reutilizada en todo ─
    hist_stats = list(
        HistorialRespuesta.objects
        .filter(tenant=tenant)
        .values('pregunta_id')
        .annotate(
            apariciones=Count('id'),
            buenas=Count('id', filter=Q(resultado='Correcto')),
            t_prom=Avg('tiempo_empleado')
        )
    )

    # ── Zonas de Dificultad + Cobertura (mismo loop) ─────────────────
    zona_critica = []
    zona_alerta  = []
    zona_peligro = []
    cobertura    = []

    for stat in hist_stats:
        pid = stat['pregunta_id']
        pq  = preguntas_cache.get(pid)
        if not pq:
            continue

        t_prom     = int(stat['t_prom'] or 0)
        apariciones = stat['apariciones']
        buenas      = stat['buenas']
        malas       = apariciones - buenas
        tasa_error  = round(malas / apariciones * 100) if apariciones else 0
        prog        = progreso_map.get(pid)

        item_zona = {'pregunta': pq, 't_prom': t_prom, 'tasa_error': tasa_error, 'n': apariciones}

        if t_prom > 180:
            zona_peligro.append(item_zona)
        elif tasa_error >= 50 or t_prom > 90:
            zona_critica.append(item_zona)
        elif 60 <= t_prom <= 180:
            zona_alerta.append(item_zona)

        # Cobertura total
        cobertura.append({
            'pregunta':    pq,
            'apariciones': apariciones,
            'buenas':      buenas,
            'malas':       malas,
            't_prom':      t_prom,
            'racha_limpia': bool(prog and prog.dominada),
            'solo_buenas':  malas == 0 and apariciones > 0,
            'racha':        prog.racha_correcta if prog else 0,
        })

    zona_peligro.sort(key=lambda x: -x['t_prom'])
    zona_critica.sort(key=lambda x: -x['tasa_error'])
    zona_alerta.sort(key=lambda x: -x['t_prom'])
    cobertura.sort(key=lambda x: x['pregunta'].numero)

    # ── Inestables ────────────────────────────────────────────────────
    inestables = [
        {'pregunta': preguntas_cache[pid], 'racha': p.racha_correcta}
        for pid, p in progreso_map.items()
        if p.inestable and pid in preguntas_cache
    ]

    # ── Ladrones de Tiempo (>90s) ─────────────────────────────────────
    ladrones = sorted(
        [i for i in (zona_peligro + zona_critica + zona_alerta) if i['t_prom'] > 90],
        key=lambda x: -x['t_prom']
    )

    # ── Total zona para botón Examen Zona ─────────────────────────────
    zona_ids_set = set(
        i['pregunta'].pk
        for i in (zona_peligro + zona_critica + zona_alerta + inestables)
    )

    # ── Resumen cobertura ─────────────────────────────────────────────
    cob_dominadas  = sum(1 for c in cobertura if c['racha_limpia'])
    cob_solo_ok    = sum(1 for c in cobertura if c['solo_buenas'] and not c['racha_limpia'])
    cob_con_fallas = sum(1 for c in cobertura if c['malas'] > 0)

    return render(request, 'simulador/inicio.html', {
        'total':         total,
        'categorias':    categorias,
        'dominadas':     dominadas,
        'fallidas':      fallidas,
        'tenant':        tenant,
        'zona_critica':  zona_critica[:10],
        'zona_alerta':   zona_alerta[:10],
        'zona_peligro':  zona_peligro[:10],
        'sin_ver_count': sin_ver_count,
        'inestables':    inestables[:10],
        'ladrones':      ladrones,
        'total_zona':    len(zona_ids_set),
        'cobertura':     cobertura,
        'cob_dominadas': cob_dominadas,
        'cob_solo_ok':   cob_solo_ok,
        'cob_con_fallas':cob_con_fallas,
    })


# ─────────────────────────────────────────────
# Examen (blind mode, timer, Next/Back)
# ─────────────────────────────────────────────

def examen_iniciar(request):
    ids = list(Pregunta.objects.values_list('id', flat=True))
    seleccion = random.sample(ids, min(EXAM_TOTAL, len(ids)))
    request.session['exam'] = {
        'preguntas': seleccion,
        'index': 0,
        'respuestas': {},
        'resultados_parcial': {},
        'terminado': False,
        'inicio_ts': int(time.time()),
        'tipo': 'normal',
    }
    return redirect('examen_pregunta')


def examen_inteligente_iniciar(request):
    tenant = _get_tenant(request)
    seleccion = _seleccionar_ponderado(tenant, EXAM_TOTAL)
    if not seleccion:
        seleccion = random.sample(
            list(Pregunta.objects.values_list('id', flat=True)),
            min(EXAM_TOTAL, Pregunta.objects.count())
        )
    request.session['exam'] = {
        'preguntas': seleccion,
        'index': 0,
        'respuestas': {},
        'resultados_parcial': {},
        'terminado': False,
        'inicio_ts': int(time.time()),
        'tipo': 'inteligente',
    }
    return redirect('examen_pregunta')


def repaso_iniciar(request):
    tenant = _get_tenant(request)
    ids_fallidas = [
        p.pregunta_id
        for p in ProgresoPregunta.objects.filter(tenant=tenant).select_related('pregunta')
        if p.fallida
    ]
    if not ids_fallidas:
        return render(request, 'simulador/repaso_vacio.html', {'tenant': tenant})
    random.shuffle(ids_fallidas)
    request.session['exam'] = {
        'preguntas': ids_fallidas,
        'index': 0,
        'respuestas': {},
        'resultados_parcial': {},
        'terminado': False,
        'inicio_ts': int(time.time()),
        'tipo': 'repaso',
    }
    return redirect('examen_pregunta')


def examen_ineditas_iniciar(request):
    tenant = _get_tenant(request)
    vistas_ids = set(ProgresoPregunta.objects
                     .filter(tenant=tenant, veces_vista__gt=0)
                     .values_list('pregunta_id', flat=True))
    ids_ineditas = list(Pregunta.objects
                        .exclude(id__in=vistas_ids)
                        .values_list('id', flat=True))
    if not ids_ineditas:
        return render(request, 'simulador/ineditas_vacio.html', {'tenant': tenant})
    random.shuffle(ids_ineditas)
    seleccion = ids_ineditas[:EXAM_TOTAL]
    request.session['exam'] = {
        'preguntas': seleccion,
        'index': 0,
        'respuestas': {},
        'resultados_parcial': {},
        'terminado': False,
        'inicio_ts': int(time.time()),
        'tipo': 'ineditas',
    }
    return redirect('examen_pregunta')


def examen_zona_iniciar(request):
    """Examen de Zona: solo preguntas difíciles, cada una debe responderse correctamente
    3 veces. Un solo error termina el examen como fallido (requiere 100%)."""
    tenant = _get_tenant(request)

    stats_qs = (HistorialRespuesta.objects
                .filter(tenant=tenant)
                .values('pregunta_id')
                .annotate(
                    total_intentos=Count('id'),
                    correctas_count=Count('id', filter=Q(resultado='Correcto')),
                    t_prom=Avg('tiempo_empleado')
                ))

    zona_ids = set()
    for stat in stats_qs:
        t_prom = int(stat['t_prom'] or 0)
        n = stat['total_intentos']
        tasa_error = round((1 - stat['correctas_count'] / n) * 100) if n else 0
        if t_prom > 90 or tasa_error >= 50:
            zona_ids.add(stat['pregunta_id'])

    # Incluir inestables
    for p in ProgresoPregunta.objects.filter(tenant=tenant, alguna_vez_dominada=True):
        if p.inestable:
            zona_ids.add(p.pregunta_id)

    zona_ids = list(zona_ids)
    if not zona_ids:
        return render(request, 'simulador/zona_vacio.html', {'tenant': tenant})

    # Secuencia: 3 rondas, cada ronda barajada distinto
    secuencia = []
    for _ in range(3):
        ronda = list(zona_ids)
        random.shuffle(ronda)
        secuencia.extend(ronda)

    request.session['exam'] = {
        'preguntas': secuencia,
        'index': 0,
        'respuestas': {},
        'resultados_parcial': {},
        'terminado': False,
        'inicio_ts': int(time.time()),
        'tipo': 'zona_master',
        'fallido': False,
        'preguntas_unicas': zona_ids,
        'meta_aprobaciones': 3,
    }
    return redirect('examen_pregunta')


def examen_pregunta(request):
    exam = request.session.get('exam')
    if not exam:
        return redirect('inicio')
    if exam.get('terminado'):
        return redirect('examen_resultado')

    idx = exam['index']
    preguntas = exam['preguntas']
    total = len(preguntas)

    if idx >= total:
        exam['terminado'] = True
        request.session['exam'] = exam
        request.session.modified = True
        return redirect('examen_resultado')

    pregunta = get_object_or_404(Pregunta, pk=preguntas[idx])
    elapsed = int(time.time()) - exam.get('inicio_ts', int(time.time()))
    remaining = max(0, EXAM_MINUTOS * 60 - elapsed)

    if remaining == 0:
        exam['terminado'] = True
        request.session['exam'] = exam
        request.session.modified = True
        return redirect('examen_resultado')

    # ── Barajado de alternativas (se genera una vez y persiste en sesión) ──
    shuf_key = f'shuf_{pregunta.pk}'
    if shuf_key not in exam:
        ops_barajadas, correcta_nueva = _barajar_opciones(pregunta.opciones, pregunta.respuesta_correcta)
        exam[shuf_key] = {'ops': ops_barajadas, 'cor': correcta_nueva}
        request.session['exam'] = exam
        request.session.modified = True
    opciones_display = exam[shuf_key]['ops']

    respuesta_previa = exam['respuestas'].get(str(pregunta.pk), '')
    rp = exam.get('resultados_parcial', {})
    correctas_parcial   = sum(1 for v in rp.values() if v)
    incorrectas_parcial = sum(1 for v in rp.values() if not v)

    return render(request, 'simulador/examen_pregunta.html', {
        'pregunta': pregunta,
        'opciones_display': opciones_display,
        'numero': idx + 1,
        'total': total,
        'progreso': int(idx / total * 100),
        'remaining': remaining,
        'respuesta_previa': respuesta_previa,
        'puede_retroceder': idx > 0,
        'es_ultima': idx == total - 1,
        'tipo': exam.get('tipo', 'normal'),
        'correctas': correctas_parcial,
        'incorrectas': incorrectas_parcial,
    })


@require_POST
def examen_navegar(request):
    exam = request.session.get('exam')
    if not exam:
        return JsonResponse({'error': 'sin_examen'}, status=400) \
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' \
            else redirect('inicio')

    action = request.POST.get('action', 'next')
    pregunta_id = request.POST.get('pregunta_id', '')
    respuesta = request.POST.get('respuesta', '').strip()
    try:
        tiempo_empleado = int(request.POST.get('tiempo_empleado', 0))
    except (ValueError, TypeError):
        tiempo_empleado = 0

    # ── Back: guarda selección actual y retrocede ──────────────────
    if action == 'back':
        if pregunta_id and respuesta:
            exam['respuestas'][str(pregunta_id)] = respuesta
        if exam['index'] > 0:
            exam['index'] -= 1
        request.session['exam'] = exam
        request.session.modified = True
        return redirect('examen_pregunta')

    # ── Finalizar (timer o botón final): POST normal ───────────────
    if action == 'finalizar':
        if pregunta_id and respuesta:
            exam['respuestas'][str(pregunta_id)] = respuesta
            try:
                pq = Pregunta.objects.get(pk=pregunta_id)
                shuf_data = exam.get(f'shuf_{pregunta_id}', {})
                correcta_actual = shuf_data.get('cor', pq.respuesta_correcta)
                exam.setdefault('resultados_parcial', {})[str(pregunta_id)] = \
                    _es_correcto(respuesta, correcta_actual)
                exam.setdefault('tiempos', {})[str(pregunta_id)] = tiempo_empleado
            except Pregunta.DoesNotExist:
                pass
        exam['terminado'] = True
        request.session['exam'] = exam
        request.session.modified = True
        return redirect('examen_resultado')

    # ── Next: AJAX — verifica, guarda y devuelve feedback ─────────
    es_correcto = False
    respuesta_correcta = ''
    tip = ''

    if pregunta_id and respuesta:
        try:
            pq = Pregunta.objects.get(pk=pregunta_id)
            shuf_data = exam.get(f'shuf_{pregunta_id}', {})
            correcta_actual = shuf_data.get('cor', pq.respuesta_correcta)

            es_correcto = _es_correcto(respuesta, correcta_actual)

            ops_display = shuf_data.get('ops', pq.opciones)
            respuesta_correcta = next(
                (op for op in ops_display if _letra(op) == _letra(correcta_actual)),
                correcta_actual
            )
            tip = _tip_espanol(pq, es_correcto)
            exam['respuestas'][str(pregunta_id)] = respuesta
            exam.setdefault('resultados_parcial', {})[str(pregunta_id)] = es_correcto
            exam.setdefault('tiempos', {})[str(pregunta_id)] = tiempo_empleado
        except Pregunta.DoesNotExist:
            pass

    # ── Zona Master: fallo inmediato si se equivoca ────────────────
    fallido = False
    if exam.get('tipo') == 'zona_master' and not es_correcto and pregunta_id:
        exam['fallido'] = True
        exam['terminado'] = True
        exam['pregunta_fallida_id'] = str(pregunta_id)
        fallido = True

    if not fallido:
        exam['index'] += 1
        terminado = exam['index'] >= len(exam['preguntas'])
        if terminado:
            exam['terminado'] = True
    else:
        terminado = True

    request.session['exam'] = exam
    request.session.modified = True

    rp = exam.get('resultados_parcial', {})
    return JsonResponse({
        'es_correcto':        es_correcto,
        'respuesta_correcta': respuesta_correcta,
        'tip':                tip,
        'terminado':          terminado,
        'fallido':            fallido,
        'correctas':          sum(1 for v in rp.values() if v),
        'incorrectas':        sum(1 for v in rp.values() if not v),
    })


def examen_resultado(request):
    exam = request.session.get('exam')
    if not exam:
        return redirect('inicio')

    tenant = _get_tenant(request)
    correctas = 0
    resultados = []

    for pid in exam['preguntas']:
        try:
            pregunta = Pregunta.objects.get(pk=pid)
        except Pregunta.DoesNotExist:
            continue

        respuesta_shuffled = exam['respuestas'].get(str(pid), '')
        shuf_data = exam.get(f'shuf_{pid}', {})

        if respuesta_shuffled:
            if shuf_data:
                correcta_actual = shuf_data.get('cor', pregunta.respuesta_correcta)
                es_correcto = _es_correcto(respuesta_shuffled, correcta_actual)
                # Mapear la respuesta barajada de vuelta a la opción original de BD
                resp_texto = _texto_sin_letra(respuesta_shuffled)
                respuesta_original = next(
                    (op for op in pregunta.opciones if _texto_sin_letra(op) == resp_texto),
                    respuesta_shuffled
                )
            else:
                es_correcto = _es_correcto(respuesta_shuffled, pregunta.respuesta_correcta)
                respuesta_original = respuesta_shuffled
        else:
            es_correcto = False
            respuesta_original = ''

        if es_correcto:
            correctas += 1

        if respuesta_shuffled:
            _registrar_progreso(tenant, pregunta, es_correcto)
            tiempo = exam.get('tiempos', {}).get(str(pid), 0)
            HistorialRespuesta.objects.create(
                tenant=tenant,
                pregunta=pregunta,
                tiempo_empleado=tiempo,
                resultado='Correcto' if es_correcto else 'Incorrecto'
            )

        resultados.append({
            'pregunta': pregunta,
            'respuesta_dada_norm': _opcion_por_letra(pregunta, respuesta_original),
            'correcta_norm': _opcion_por_letra(pregunta, pregunta.respuesta_correcta),
            'es_correcto': es_correcto,
            'tip': _tip_espanol(pregunta, es_correcto),
        })

    tipo = exam.get('tipo', 'normal')
    fallido_zona = exam.get('fallido', False)
    pregunta_fallida = None
    if fallido_zona and exam.get('pregunta_fallida_id'):
        try:
            pregunta_fallida = Pregunta.objects.get(pk=exam['pregunta_fallida_id'])
        except Pregunta.DoesNotExist:
            pass

    total_unicas = len(set(exam['preguntas'])) if tipo == 'zona_master' else len(exam['preguntas'])
    total = len(exam['preguntas'])
    incorrectas = total - correctas
    porcentaje = int(correctas / total * 100) if total else 0

    if tipo == 'zona_master':
        aprobado = not fallido_zona and incorrectas == 0
    else:
        aprobado = correctas >= PASS_SCORE

    request.session.pop('exam', None)

    return render(request, 'simulador/examen_resultado.html', {
        'correctas': correctas,
        'incorrectas': incorrectas,
        'total': total,
        'total_unicas': total_unicas,
        'porcentaje': porcentaje,
        'aprobado': aprobado,
        'pass_score': PASS_SCORE,
        'resultados': resultados,
        'tipo': tipo,
        'fallido_zona': fallido_zona,
        'pregunta_fallida': pregunta_fallida,
        'tenant': tenant,
    })


# ─────────────────────────────────────────────
# Modo Estudio (feedback inmediato)
# ─────────────────────────────────────────────

def quiz(request):
    tenant = _get_tenant(request)
    sk = f't{tenant.id}_'
    modo = request.GET.get('modo', 'aleatorio')

    if request.GET.get('reiniciar'):
        request.session.pop(f'{sk}vistas', None)
        request.session.pop(f'{sk}correctas', None)
        request.session.pop(f'{sk}incorrectas', None)

    vistas = set(request.session.get(f'{sk}vistas', []))
    correctas = request.session.get(f'{sk}correctas', 0)
    incorrectas = request.session.get(f'{sk}incorrectas', 0)

    qs = Pregunta.objects.all()
    if modo.startswith('cat_'):
        cat = modo[4:].replace('_', ' ')
        qs = qs.filter(categoria=cat)
    elif modo.startswith('pagina_'):
        try:
            qs = qs.filter(pagina=int(modo.split('_')[1]))
        except (ValueError, IndexError):
            pass
    elif modo.startswith('pregunta_'):
        try:
            qs = qs.filter(pk=int(modo.split('_')[1]))
        except (ValueError, IndexError):
            pass
    elif modo == 'repaso':
        ids_fallidas = [
            p.pregunta_id
            for p in ProgresoPregunta.objects.filter(tenant=tenant)
            if p.fallida
        ]
        qs = qs.filter(id__in=ids_fallidas) if ids_fallidas else qs.none()

    pendientes = qs.exclude(numero__in=vistas)

    if not pendientes.exists():
        return render(request, 'simulador/completado.html', {
            'correctas': correctas,
            'incorrectas': incorrectas,
            'total': len(vistas),
            'modo': modo,
            'tenant': tenant,
        })

    pregunta = random.choice(list(pendientes))
    total_modo = qs.count()

    # ── Barajar alternativas ──────────────────────────────────────────
    ops_barajadas, correcta_nueva = _barajar_opciones(pregunta.opciones, pregunta.respuesta_correcta)
    request.session[f'{sk}shuf_{pregunta.pk}'] = {'ops': ops_barajadas, 'cor': correcta_nueva}

    return render(request, 'simulador/quiz.html', {
        'pregunta': pregunta,
        'opciones_display': ops_barajadas,
        'modo': modo,
        'vistas': len(vistas),
        'total_modo': total_modo,
        'correctas': correctas,
        'incorrectas': incorrectas,
        'progreso': int(len(vistas) / total_modo * 100) if total_modo else 0,
        'tenant': tenant,
    })


@require_POST
@ratelimit(key='ip', rate='60/m', block=True)
def verificar(request):
    tenant = _get_tenant(request)
    sk = f't{tenant.id}_'
    pregunta_id = request.POST.get('pregunta_id')
    respuesta = request.POST.get('respuesta', '').strip()
    modo = request.POST.get('modo', 'aleatorio')
    try:
        tiempo_empleado = int(request.POST.get('tiempo_empleado', 0))
    except (ValueError, TypeError):
        tiempo_empleado = 0

    pregunta = get_object_or_404(Pregunta, pk=pregunta_id)

    # Usar el mapa de barajado de la sesión para validar correctamente
    shuf = request.session.get(f'{sk}shuf_{pregunta.pk}', {})
    if shuf:
        correcta_actual = shuf.get('cor', pregunta.respuesta_correcta)
        ops_display = shuf.get('ops', pregunta.opciones)
    else:
        correcta_actual = pregunta.respuesta_correcta
        ops_display = pregunta.opciones

    es_correcto = _es_correcto(respuesta, correcta_actual)

    opcion_correcta_display = next(
        (op for op in ops_display if _letra(op) == _letra(correcta_actual)),
        correcta_actual
    )

    vistas = set(request.session.get(f'{sk}vistas', []))
    vistas.add(pregunta.numero)
    request.session[f'{sk}vistas'] = list(vistas)

    if es_correcto:
        request.session[f'{sk}correctas'] = request.session.get(f'{sk}correctas', 0) + 1
    else:
        request.session[f'{sk}incorrectas'] = request.session.get(f'{sk}incorrectas', 0) + 1

    _registrar_progreso(tenant, pregunta, es_correcto)

    HistorialRespuesta.objects.create(
        tenant=tenant,
        pregunta=pregunta,
        tiempo_empleado=tiempo_empleado,
        resultado='Correcto' if es_correcto else 'Incorrecto'
    )

    return JsonResponse({
        'correcto': es_correcto,
        'respuesta_correcta': opcion_correcta_display,
        'explicacion': pregunta.explicacion,
        'tip': _tip_espanol(pregunta, es_correcto),
    })


# ─────────────────────────────────────────────
# Progreso
# ─────────────────────────────────────────────

def progreso(request):
    tenant = _get_tenant(request)
    registros = (ProgresoPregunta.objects
                 .filter(tenant=tenant)
                 .select_related('pregunta')
                 .order_by('-veces_vista', '-veces_correcta'))

    total_q = Pregunta.objects.count()
    dominadas = [r for r in registros if r.dominada]
    en_progreso = [r for r in registros if r.fallida]
    sin_ver = total_q - registros.count()

    cats = {}
    for r in registros:
        cat = r.pregunta.categoria
        if cat not in cats:
            cats[cat] = {'dominadas': 0, 'total_vistas': 0}
        cats[cat]['total_vistas'] += 1
        if r.dominada:
            cats[cat]['dominadas'] += 1

    return render(request, 'simulador/progreso.html', {
        'dominadas': dominadas,
        'en_progreso': en_progreso,
        'sin_ver': sin_ver,
        'total_q': total_q,
        'cats': cats,
        'pct_dom': int(len(dominadas) / total_q * 100) if total_q else 0,
        'tenant': tenant,
    })
