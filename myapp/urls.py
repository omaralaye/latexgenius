from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('login/', views.login_page, name='login'),
    path('signup/', views.signup_page, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_page, name='dashboard'),
    path('settings/', views.settings_page, name='settings'),
    path('editor/', views.editor_page, name='editor'),
    path('editor/<str:project_id>/', views.editor_page, name='editor_with_id'),
    path('editor/<str:project_id>/save/', views.save_project, name='save_project'),
    path('editor/<str:project_id>/compile/', views.compile_project, name='compile_project'),
    path('templates/', views.templates_page, name='templates'),
]
