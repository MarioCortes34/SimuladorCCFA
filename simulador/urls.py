from django.urls import path
from . import views

urlpatterns = [
    path("",                       views.inicio,                    name="inicio"),
    path("tenant/",                views.seleccionar_tenant,        name="seleccionar_tenant"),
    path("examen/iniciar/",        views.examen_iniciar,            name="examen_iniciar"),
    path("examen/inteligente/",    views.examen_inteligente_iniciar, name="examen_inteligente"),
    path("examen/pregunta/",       views.examen_pregunta,           name="examen_pregunta"),
    path("examen/navegar/",        views.examen_navegar,            name="examen_navegar"),
    path("examen/resultado/",      views.examen_resultado,          name="examen_resultado"),
    path("repaso/",                views.repaso_iniciar,            name="repaso_iniciar"),
    path("examen/ineditas/",       views.examen_ineditas_iniciar,   name="examen_ineditas"),
    path("examen/zona/",           views.examen_zona_iniciar,       name="examen_zona"),
    path("examen/zona/repaso/<str:zona>/", views.examen_zona_repaso_iniciar, name="examen_zona_repaso"),
    path("examen/topico/<slug:topic_slug>/", views.examen_topico_iniciar,  name="examen_topico"),
    path("quiz/",                  views.quiz,                      name="quiz"),
    path("verificar/",             views.verificar,                 name="verificar"),
    path("progreso/",              views.progreso,                  name="progreso"),
]
