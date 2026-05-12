import re
import random
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
from .models import Pregunta, ProgresoPregunta

PASS_SCORE   = 45
EXAM_TOTAL   = 60


def _letra(texto: str) -> str:
    """
    Extrae la letra de una opción (A, B, C, D).
    Funciona con formatos: 'A. texto', 'A) texto', 'A:texto' o solo 'A'.
    Devuelve la letra en mayúscula, o el texto completo en minúscula como fallback.
    """
    m = re.match(r'^\s*([A-Da-d])[\.\)\:]\s*', texto.strip())
    if m:
        return m.group(1).upper()
    t = texto.strip()
    if len(t) == 1 and t.isalpha():
        return t.upper()
    return texto.strip().lower()


def _es_correcto(respuesta: str, correcta: str) -> bool:
    """Compara solo la letra de la opción para evitar falsos positivos por substring."""
    return _letra(respuesta) == _letra(correcta)


def _tip_espanol(pregunta, es_correcto: bool) -> str:
    """
    Genera un tip en español analizando el enunciado en inglés.
    Detecta palabras trampa (EXCEPT, BEST, ONLY, etc.) y explica qué buscar.
    """
    txt = pregunta.enunciado.upper()
    partes = []

    # Palabras trampa más comunes en exámenes de certificación
    if any(w in txt for w in ['EXCEPT', 'NOT INCLUDE', 'CANNOT', 'DOES NOT', 'NOT TRUE', 'NOT CORRECT']):
        partes.append('⚠️ <b>Negación:</b> La pregunta pide la EXCEPCIÓN — busca la opción que NO cumple la condición, no la que sí.')

    if any(w in txt for w in ['BEST', 'MOST LIKELY', 'MOST APPROPRIATE', 'PRIMARY', 'MAIN REASON', 'MAIN PURPOSE']):
        partes.append('🎯 <b>La "mejor" opción:</b> Varias respuestas pueden ser parcialmente correctas. Elige la que responde MÁS directamente a lo que pide.')

    if any(w in txt for w in ['ONLY', 'ALWAYS', 'NEVER', 'ALL OF THE']):
        partes.append('⚡ <b>Absolutos (ONLY/ALWAYS/NEVER):</b> Son señales de alerta — si hay aunque sea una excepción, esa opción es falsa.')

    if any(w in txt for w in ['FIRST', 'INITIAL STEP', 'BEFORE', 'PRIOR TO']):
        partes.append('📋 <b>Orden/Prioridad:</b> No solo qué es correcto, sino qué va PRIMERO. Piensa en el flujo del proceso.')

    if any(w in txt for w in ['IMMEDIATELY', 'REAL-TIME', 'WITHOUT']):
        partes.append('⚡ <b>Inmediatez:</b> La respuesta implica una acción en tiempo real o sin pasos intermedios.')

    if any(w in txt for w in ['AID', 'CID', 'AGENT ID', 'CUSTOMER ID']):
        partes.append('🔑 <b>AID vs CID:</b> AID = Agent ID (identificador del sensor/host). CID = Customer ID (identificador de tu organización).')

    if any(w in txt for w in ['IOA', 'IOC', 'INDICATOR']):
        partes.append('🔍 <b>IOA vs IOC:</b> IOA = comportamiento (qué hace el atacante, fileless). IOC = evidencia forense (hashes, IPs, dominios).')

    if any(w in txt for w in ['RFM', 'REDUCED FUNCTIONALITY']):
        partes.append('⚙️ <b>RFM:</b> Reduced Functionality Mode — el sensor es incompatible con el Kernel del OS.')

    if any(w in txt for w in ['RTR', 'REAL TIME RESPONSE']):
        partes.append('🖥️ <b>RTR:</b> Consola remota interactiva. Sus logs se retienen solo 90 días (vs 365 de otros logs).')

    if any(w in txt for w in ['SENSOR VISIBILITY', 'EXCLUSION']):
        partes.append('🚫 <b>Exclusiones:</b> Sensor Visibility Exclusions crean un PUNTO CIEGO — la actividad maliciosa en rutas excluidas NO se detecta ni previene.')

    if any(w in txt for w in ['OVERWATCH', 'THREAT HUNT']):
        partes.append('👁️ <b>OverWatch:</b> Es el equipo HUMANO de CrowdStrike que caza amenazas 24/7. No es un módulo de software.')

    # Si no encontramos palabras clave específicas
    if not partes:
        partes.append('💡 <b>Tip:</b> Lee cada opción completa. En preguntas técnicas, la diferencia suele estar en UNA palabra clave.')

    # Si tiene explicación del scraping, agregarla
    if pregunta.explicacion:
        partes.append(f'📖 <b>Explicación:</b> {pregunta.explicacion}')

    return '<br>'.join(partes)


# ─────────────────────────────────────────────
# Utilidades de sesión
# ─────────────────────────────────────────────

def _ensure_session(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def _registrar_progreso(request, pregunta, es_correcto):
    sk = _ensure_session(request)
    obj, _ = ProgresoPregunta.objects.get_or_create(
        session_key=sk, pregunta=pregunta
    )
    obj.veces_vista    += 1
    obj.veces_correcta += 1 if es_correcto else 0
    obj.save()


# ─────────────────────────────────────────────
# Inicio
# ─────────────────────────────────────────────

def inicio(request):
    total       = Pregunta.objects.count()
    categorias  = (Pregunta.objects.values_list('categoria', flat=True)
                                   .distinct().order_by('categoria'))
    sk          = _ensure_session(request)
    dominadas   = ProgresoPregunta.objects.filter(
        session_key=sk, veces_vista__gte=2
    ).count()
    return render(request, 'simulador/inicio.html', {
        'total':      total,
        'categorias': categorias,
        'dominadas':  dominadas,
    })


# ─────────────────────────────────────────────
# Examen oficial (60 preguntas, puntaje, aprobado/reprobado)
# ─────────────────────────────────────────────

def examen_iniciar(request):
    """Selecciona 60 preguntas al azar y guarda el estado del examen en sesión."""
    ids = list(Pregunta.objects.values_list('id', flat=True))
    if len(ids) < EXAM_TOTAL:
        seleccion = ids
    else:
        seleccion = random.sample(ids, EXAM_TOTAL)

    request.session['exam'] = {
        'preguntas':  seleccion,
        'index':      0,
        'respuestas': {},
        'correctas':  0,
        'terminado':  False,
    }
    return redirect('examen_pregunta')


def examen_pregunta(request):
    """Muestra la pregunta actual del examen."""
    exam = request.session.get('exam')
    if not exam:
        return redirect('inicio')

    if exam['terminado'] or exam['index'] >= len(exam['preguntas']):
        return redirect('examen_resultado')

    idx      = exam['index']
    total    = len(exam['preguntas'])
    pregunta = get_object_or_404(Pregunta, pk=exam['preguntas'][idx])

    return render(request, 'simulador/examen_pregunta.html', {
        'pregunta':  pregunta,
        'numero':    idx + 1,
        'total':     total,
        'progreso':  int(idx / total * 100),
        'correctas': exam['correctas'],
    })


@require_POST
@ratelimit(key='ip', rate='60/m', block=True)
def examen_verificar(request):
    """Verifica la respuesta del examen (AJAX) y avanza al siguiente."""
    exam = request.session.get('exam')
    if not exam:
        return JsonResponse({'error': 'Sin examen activo'}, status=400)

    pregunta_id = request.POST.get('pregunta_id')
    respuesta   = request.POST.get('respuesta', '').strip().lower()
    pregunta    = get_object_or_404(Pregunta, pk=pregunta_id)
    correcta    = pregunta.respuesta_correcta.strip().lower()

    es_correcto = _es_correcto(respuesta, correcta)

    # Guardar respuesta y avanzar índice
    exam['respuestas'][str(pregunta_id)] = respuesta
    if es_correcto:
        exam['correctas'] += 1
    exam['index'] += 1

    if exam['index'] >= len(exam['preguntas']):
        exam['terminado'] = True

    request.session['exam'] = exam
    request.session.modified = True

    _registrar_progreso(request, pregunta, es_correcto)

    return JsonResponse({
        'correcto':           es_correcto,
        'respuesta_correcta': pregunta.respuesta_correcta,
        'explicacion':        pregunta.explicacion,
        'tip':                _tip_espanol(pregunta, es_correcto),
        'terminado':          exam['terminado'],
    })


def examen_resultado(request):
    """Muestra el resultado final del examen."""
    exam = request.session.get('exam')
    if not exam:
        return redirect('inicio')

    correctas   = exam['correctas']
    total       = len(exam['preguntas'])
    incorrectas = total - correctas
    porcentaje  = int(correctas / total * 100) if total else 0
    aprobado    = correctas >= PASS_SCORE

    # Limpiar examen de la sesión
    request.session.pop('exam', None)

    return render(request, 'simulador/examen_resultado.html', {
        'correctas':   correctas,
        'incorrectas': incorrectas,
        'total':       total,
        'porcentaje':  porcentaje,
        'aprobado':    aprobado,
        'pass_score':  PASS_SCORE,
    })


# ─────────────────────────────────────────────
# Modo Estudio (pregunta a pregunta, sin límite)
# ─────────────────────────────────────────────

def quiz(request):
    modo = request.GET.get('modo', 'aleatorio')

    if request.GET.get('reiniciar'):
        request.session.pop('vistas', None)
        request.session.pop('correctas', None)
        request.session.pop('incorrectas', None)

    vistas      = set(request.session.get('vistas', []))
    correctas   = request.session.get('correctas', 0)
    incorrectas = request.session.get('incorrectas', 0)

    qs = Pregunta.objects.all()
    if modo.startswith('cat_'):
        cat = modo[4:].replace('_', ' ')
        qs  = qs.filter(categoria=cat)
    elif modo.startswith('pagina_'):
        try:
            qs = qs.filter(pagina=int(modo.split('_')[1]))
        except (ValueError, IndexError):
            pass

    pendientes = qs.exclude(numero__in=vistas)

    if not pendientes.exists():
        return render(request, 'simulador/completado.html', {
            'correctas':   correctas,
            'incorrectas': incorrectas,
            'total':       len(vistas),
            'modo':        modo,
        })

    pregunta   = random.choice(list(pendientes))
    total_modo = qs.count()

    return render(request, 'simulador/quiz.html', {
        'pregunta':    pregunta,
        'modo':        modo,
        'vistas':      len(vistas),
        'total_modo':  total_modo,
        'correctas':   correctas,
        'incorrectas': incorrectas,
        'progreso':    int(len(vistas) / total_modo * 100) if total_modo else 0,
    })


@require_POST
@ratelimit(key='ip', rate='60/m', block=True)
def verificar(request):
    pregunta_id = request.POST.get('pregunta_id')
    respuesta   = request.POST.get('respuesta', '').strip().lower()
    modo        = request.POST.get('modo', 'aleatorio')
    pregunta    = get_object_or_404(Pregunta, pk=pregunta_id)
    correcta    = pregunta.respuesta_correcta.strip().lower()

    es_correcto = _es_correcto(respuesta, correcta)

    vistas = set(request.session.get('vistas', []))
    vistas.add(pregunta.numero)
    request.session['vistas'] = list(vistas)

    if es_correcto:
        request.session['correctas'] = request.session.get('correctas', 0) + 1
    else:
        request.session['incorrectas'] = request.session.get('incorrectas', 0) + 1

    _registrar_progreso(request, pregunta, es_correcto)

    return JsonResponse({
        'correcto':           es_correcto,
        'respuesta_correcta': pregunta.respuesta_correcta,
        'explicacion':        pregunta.explicacion,
        'tip':                _tip_espanol(pregunta, es_correcto),
    })


# ─────────────────────────────────────────────
# Dashboard de Progreso / Mastery
# ─────────────────────────────────────────────

def progreso(request):
    sk         = _ensure_session(request)
    registros  = (ProgresoPregunta.objects
                  .filter(session_key=sk)
                  .select_related('pregunta')
                  .order_by('-veces_vista', '-veces_correcta'))

    total_q    = Pregunta.objects.count()
    dominadas  = [r for r in registros if r.dominada]
    en_progreso= [r for r in registros if not r.dominada]
    sin_ver    = total_q - registros.count()

    # Agrupación por categoría
    cats = {}
    for r in registros:
        cat = r.pregunta.categoria
        if cat not in cats:
            cats[cat] = {'dominadas': 0, 'total_vistas': 0}
        cats[cat]['total_vistas'] += 1
        if r.dominada:
            cats[cat]['dominadas'] += 1

    return render(request, 'simulador/progreso.html', {
        'dominadas':   dominadas,
        'en_progreso': en_progreso,
        'sin_ver':     sin_ver,
        'total_q':     total_q,
        'cats':        cats,
        'pct_dom':     int(len(dominadas) / total_q * 100) if total_q else 0,
    })
