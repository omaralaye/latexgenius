from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from . import services
from datetime import datetime
import httpx
import logging

User = get_user_model()
logger = logging.getLogger('myapp')

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

@ratelimit(key='ip', rate='10/m', method='POST', block=False)
def login_page(request):
    if getattr(request, 'limited', False):
        if request.GET.get('format') == 'json':
            return JsonResponse({"status": "error", "message": "Too many login attempts. Please try again later."}, status=429)
        messages.error(request, "Too many login attempts. Please try again later.")
        return render(request, 'pages/login.html', {'form': AuthenticationForm()})

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                logger.info(f"User logged in: {username}")
                if request.GET.get('format') == 'json':
                    return JsonResponse({"status": "success", "user_id": user.id})
                return redirect('dashboard')
            else:
                logger.warning(f"Failed login attempt for user: {username}")
        else:
            logger.warning(f"Invalid login form submission")
            if request.GET.get('format') == 'json':
                return JsonResponse({"status": "error", "message": "Invalid username or password."}, status=400)
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'pages/login.html', {'form': form})

@ratelimit(key='ip', rate='5/m', method='POST', block=False)
def signup_page(request):
    if getattr(request, 'limited', False):
        if request.GET.get('format') == 'json':
            return JsonResponse({"status": "error", "message": "Too many signup attempts. Please try again later."}, status=429)
        messages.error(request, "Too many signup attempts. Please try again later.")
        return render(request, 'pages/signup.html')

    if request.method == 'POST':
        username = request.POST.get('email')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('name')

        if User.objects.filter(username=username).exists():
            logger.warning(f"Signup failed: User already exists: {username}")
            if request.GET.get('format') == 'json':
                return JsonResponse({"status": "error", "message": "User already exists."}, status=400)
            messages.error(request, "User already exists.")
        else:
            user = User.objects.create_user(username=username, email=email, password=password, first_name=first_name)
            login(request, user)
            logger.info(f"New user signed up: {username}")
            if request.GET.get('format') == 'json':
                return JsonResponse({"status": "success", "user_id": user.id})
            return redirect('dashboard')

    return render(request, 'pages/signup.html')

def logout_view(request):
    username = request.user.username if request.user.is_authenticated else "Anonymous"
    logout(request)
    logger.info(f"User logged out: {username}")
    if request.GET.get('format') == 'json':
        return JsonResponse({"status": "success"})
    return redirect('landing')

@login_required
def dashboard_page(request):
    projects = services.get_user_projects(request.user.id)
    total_projects = len(projects)

    recent_activity = "N/A"
    if projects:
        last_modified = projects[0]['last_modified']
        diff = timezone.now() - last_modified
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
def settings_page(request):
    context = {
        'app_settings': services.get_all_settings(),
    }
    if request.GET.get('format') == 'json':
        return JsonResponse(context, safe=False)
    return render(request, 'pages/settings.html', context)

@login_required
def editor_page(request, project_id=None):
    if project_id:
        try:
            project = services.get_project_by_id(project_id)
            if not project or project['owner_id'] != request.user.id:
                 logger.warning(f"Unauthorized access attempt to project {project_id} by user {request.user.id}")
                 return JsonResponse({"status": "error", "message": "Project not found or access denied."}, status=404)
        except Exception as e:
            logger.error(f"Error accessing project {project_id}: {str(e)}")
            return JsonResponse({"status": "error", "message": "Invalid project ID."}, status=400)
    else:
        projects = services.get_user_projects(request.user.id)
        if projects:
            project = projects[0]
        else:
            logger.info(f"Creating default project for user {request.user.id}")
            project_id = services.create_project(
                owner_id=request.user.id,
                title="Untitled Project",
                content="\\documentclass{article}\n\\begin{document}\nHello World\n\\end{document}".replace('\\n', '\n')
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

@ratelimit(key='user', rate='20/m', block=False)
@login_required
def save_project(request, project_id):
    if getattr(request, 'limited', False):
        return JsonResponse({"status": "error", "message": "Too many requests. Please slow down."}, status=429)

    project = services.get_project_by_id(project_id)
    if not project or project['owner_id'] != request.user.id:
        logger.warning(f"Unauthorized save attempt to project {project_id} by user {request.user.id}")
        return JsonResponse({"status": "error", "message": "Project not found or access denied."}, status=404)

    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            content = data.get('content')
            title = data.get('title')
        except json.JSONDecodeError:
            content = request.POST.get('content')
            title = request.POST.get('title')

        update_data = {}
        if content is not None:
            update_data['content'] = content
        if title is not None:
            update_data['title'] = title

        if update_data:
            logger.info(f"Saving project {project_id} for user {request.user.id}")
            services.update_project(project_id, update_data)
            return JsonResponse({"status": "success"})

    return JsonResponse({"status": "error", "message": "Invalid request method"}, status=405)

@ratelimit(key='user', rate='10/m', block=False)
@login_required
def compile_project(request, project_id):
    if getattr(request, 'limited', False):
        return HttpResponse("Too many compilation requests. Please slow down.", status=429)

    project = services.get_project_by_id(project_id)
    if not project or project['owner_id'] != request.user.id:
        logger.warning(f"Unauthorized compilation attempt for project {project_id} by user {request.user.id}")
        return HttpResponse("Project not found or access denied.", status=404)

    content = project['content']
    logger.info(f"Compiling project {project_id} for user {request.user.id}")

    try:
        # We use a POST request to handle potentially large LaTeX content
        # LaTeX.Online supports text compilation via the 'text' parameter
        response = httpx.post(
            "https://latexonline.cc/compile",
            data={"text": content},
            timeout=60.0
        )

        if response.status_code == 200:
            logger.info(f"Compilation successful for project {project_id}")
            pdf_response = HttpResponse(response.content, content_type='application/pdf')
            pdf_response['Content-Disposition'] = f'attachment; filename="{project.get("filename", "document.pdf").replace(".tex", ".pdf")}"'
            return pdf_response
        else:
            # On failure, LaTeX.Online often returns the log in the body
            logger.error(f"Compilation failed for project {project_id}: {response.text[:100]}...")
            return HttpResponse(f"Compilation failed:\n\n{response.text}", content_type="text/plain", status=400)
    except httpx.RequestError as e:
        logger.error(f"Error connecting to LaTeX.Online for project {project_id}: {str(e)}")
        return HttpResponse(f"Error connecting to LaTeX.Online: {str(e)}", status=500)
