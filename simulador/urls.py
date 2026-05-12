from django.urls import path
from . import views

urlpatterns = [
    path("",                  views.inicio,          name="inicio"),
    path("examen/iniciar/",   views.examen_iniciar,  name="examen_iniciar"),
    path("examen/pregunta/",  views.examen_pregunta, name="examen_pregunta"),
    path("examen/verificar/", views.examen_verificar,name="examen_verificar"),
    path("examen/resultado/", views.examen_resultado, name="examen_resultado"),
    path("quiz/",             views.quiz,             name="quiz"),
    path("verificar/",        views.verificar,        name="verificar"),
    path("progreso/",         views.progreso,         name="progreso"),
]
