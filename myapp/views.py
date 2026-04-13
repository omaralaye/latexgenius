from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout, get_user_model
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from .models import Template, Project, AppSetting, Feature, Statistic, Testimonial

User = get_user_model()

def get_app_settings():
    settings = AppSetting.objects.all()
    return {s.key: s.value for s in settings}

def landing_page(request):
    features = Feature.objects.all()
    templates = Template.objects.all()[:4] # Only show 4 templates on landing
    context = {
        'features': features,
        'templates': templates,
        'app_settings': get_app_settings(),
    }
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
                return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'pages/login.html', {'form': form})

def signup_page(request):
    if request.method == 'POST':
        # Simple signup handling for demo, ideally use a custom form
        # But we'll use the provided HTML fields: name (mapped to username for simplicity or first_name), email, password
        username = request.POST.get('email')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('name')

        if User.objects.filter(username=username).exists():
            messages.error(request, "User already exists.")
        else:
            user = User.objects.create_user(username=username, email=email, password=password, first_name=first_name)
            login(request, user)
            return redirect('dashboard')

    return render(request, 'pages/signup.html')

def logout_view(request):
    logout(request)
    return redirect('landing')

@login_required
def dashboard_page(request):
    projects = Project.objects.filter(owner=request.user).order_by('-last_modified')
    total_projects = projects.count()
    # Simple recent activity: time since last modified of the most recent project
    recent_activity = "N/A"
    if projects.exists():
        from django.utils import timezone
        diff = timezone.now() - projects.first().last_modified
        if diff.days > 0:
            recent_activity = f"{diff.days}d ago"
        elif diff.seconds // 3600 > 0:
            recent_activity = f"{diff.seconds // 3600}h ago"
        else:
            recent_activity = f"{diff.seconds // 60}m ago"

    shared_projects = request.user.collaborated_projects.count()

    context = {
        'projects': projects,
        'total_projects': total_projects,
        'recent_activity': recent_activity,
        'shared_projects': shared_projects,
        'app_settings': get_app_settings(),
    }
    return render(request, 'pages/dashboardpage.html', context)

@login_required
def editor_page(request, project_id=None):
    if project_id:
        project = get_object_or_404(Project, id=project_id, owner=request.user)
    else:
        # For demo purposes, if no ID, get the first project or create a dummy one
        project = Project.objects.filter(owner=request.user).first()
        if not project:
            # Create a default project if none exists
            project = Project.objects.create(
                title="Untitled Project",
                owner=request.user,
                content=r"\documentclass{article}\n\begin{document}\nHello World\n\end{document}"
            )

    context = {
        'project': project
    }
    return render(request, 'pages/editor.html', context)

def templates_page(request):
    templates = Template.objects.all()
    stats = Statistic.objects.all()
    testimonial = Testimonial.objects.first()
    context = {
        'templates': templates,
        'stats': stats,
        'testimonial': testimonial,
        'app_settings': get_app_settings(),
    }
    return render(request, 'pages/templatespage.html', context)
