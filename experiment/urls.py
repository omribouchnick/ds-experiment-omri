# myapp/urls.py

from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing_page'),  # Landing page
    path('consent_form/', views.consent_form, name='consent_form'),  # Consent form page
    path('instructions/', views.instructions, name='instructions'),  # Instruction page
    path('end/', views.end, name='end_experiment'),  # End the experiment
    path('game/', views.game, name='game'),  # game
    path('save_db/', views.save_db, name='save_db'),  # save_db
    path('progress/', views.progress, name='progress'),
    path('login/', views.login, name='login'),
    path('fresh_restart/', views.fresh_restart, name='fresh_restart'),
    path('toast_1/', views.toast_1, name='toast_1'),
    path('toast_2/', views.toast_2, name='toast_2'),
    path('recaptcha/', views.recaptcha, name='recaptcha'),
]