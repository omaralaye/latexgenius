from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('dashboard/', views.dashboard_page, name='dashboard'),
    path('editor/', views.editor_page, name='editor'),
    path('editor/<int:project_id>/', views.editor_page, name='editor_with_id'),
    path('templates/', views.templates_page, name='templates'),
]
