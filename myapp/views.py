from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Template, Project

def landing_page(request):
    return render(request, 'pages/landingpage.html')

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
    context = {
        'templates': templates
    }
    return render(request, 'pages/templatespage.html', context)
