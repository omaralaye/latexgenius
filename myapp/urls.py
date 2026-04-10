from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('login/', views.login_page, name='login'),
    path('signup/', views.signup_page, name='signup'),
    path('dashboard/', views.dashboard_page, name='dashboard'),
    path('editor/', views.editor_page, name='editor'),
    path('editor/<int:project_id>/', views.editor_page, name='editor_with_id'),
    path('templates/', views.templates_page, name='templates'),
]
