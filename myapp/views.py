from django.shortcuts import render

def landing_page(request):
    return render(request, 'pages/landingpage.html')

def dashboard_page(request):
    return render(request, 'pages/dashboardpage.html')

def editor_page(request):
    return render(request, 'pages/editor.html')

def templates_page(request):
    return render(request, 'pages/templatespage.html')
