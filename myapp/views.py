from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.http import JsonResponse
from . import services
from datetime import datetime

User = get_user_model()

def landing_page(request):
    features = services.get_features()
    templates = services.get_templates(limit=4)
    context = {
        'features': features,
        'templates': templates,
        'app_settings': services.get_all_settings(),
    }
    if request.GET.get('format') == 'json':
        return JsonResponse(context, safe=False)
    return render(request, 'pages/landingpage.html', context)

def login_page(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                if request.GET.get('format') == 'json':
                    return JsonResponse({"status": "success", "user_id": user.id})
                return redirect('dashboard')
        else:
            if request.GET.get('format') == 'json':
                return JsonResponse({"status": "error", "message": "Invalid username or password."}, status=400)
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'pages/login.html', {'form': form})

def signup_page(request):
    if request.method == 'POST':
        username = request.POST.get('email')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('name')

        if User.objects.filter(username=username).exists():
            if request.GET.get('format') == 'json':
                return JsonResponse({"status": "error", "message": "User already exists."}, status=400)
            messages.error(request, "User already exists.")
        else:
            user = User.objects.create_user(username=username, email=email, password=password, first_name=first_name)
            login(request, user)
            if request.GET.get('format') == 'json':
                return JsonResponse({"status": "success", "user_id": user.id})
            return redirect('dashboard')

    return render(request, 'pages/signup.html')

def logout_view(request):
    logout(request)
    if request.GET.get('format') == 'json':
        return JsonResponse({"status": "success"})
    return redirect('landing')

@login_required
def dashboard_page(request):
    projects = services.get_user_projects(request.user.id)
    total_projects = len(projects)

    recent_activity = "N/A"
    if projects:
        last_modified_str = projects[0]['last_modified']
        last_modified = datetime.fromisoformat(last_modified_str)
        diff = datetime.utcnow() - last_modified
        if diff.days > 0:
            recent_activity = f"{diff.days}d ago"
        elif diff.seconds // 3600 > 0:
            recent_activity = f"{diff.seconds // 3600}h ago"
        else:
            recent_activity = f"{diff.seconds // 60}m ago"

    shared_projects_count = services.get_shared_projects_count(request.user.id)

    context = {
        'projects': projects,
        'total_projects': total_projects,
        'recent_activity': recent_activity,
        'shared_projects': shared_projects_count,
        'app_settings': services.get_all_settings(),
    }
    if request.GET.get('format') == 'json':
        return JsonResponse(context, safe=False)
    return render(request, 'pages/dashboardpage.html', context)

@login_required
def editor_page(request, project_id=None):
    if project_id:
        try:
            project = services.get_project_by_id(project_id)
            if not project or project['owner_id'] != request.user.id:
                 return JsonResponse({"status": "error", "message": "Project not found or access denied."}, status=404)
        except Exception:
            return JsonResponse({"status": "error", "message": "Invalid project ID."}, status=400)
    else:
        projects = services.get_user_projects(request.user.id)
        if projects:
            project = projects[0]
        else:
            project_id = services.create_project(
                owner_id=request.user.id,
                title="Untitled Project",
                content=r"\documentclass{article}\n\begin{document}\nHello World\n\end{document}"
            )
            project = services.get_project_by_id(project_id)

    context = {
        'project': project
    }
    if request.GET.get('format') == 'json':
        return JsonResponse(context, safe=False)
    return render(request, 'pages/editor.html', context)

def templates_page(request):
    templates = services.get_templates()
    stats = services.get_statistics()
    testimonials = services.get_testimonials()
    testimonial = testimonials[0] if testimonials else None

    context = {
        'templates': templates,
        'stats': stats,
        'testimonial': testimonial,
        'app_settings': services.get_all_settings(),
    }
    if request.GET.get('format') == 'json':
        return JsonResponse(context, safe=False)
    return render(request, 'pages/templatespage.html', context)
