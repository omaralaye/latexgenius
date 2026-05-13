from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.conf import settings
from django_ratelimit.decorators import ratelimit
from . import services
from .models import Profile
from datetime import datetime
import httpx
import logging
import io
import tarfile
import pypandoc
import os
import tempfile
import tempfile
from urllib.parse import urlencode

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

import os

@login_required
def ai_convert(request):
    if request.method == 'POST':
        content = request.POST.get('content')
        uploaded_file = request.FILES.get('document')
        title = "AI Project"

        template_id = request.POST.get('template_id')
        if not template_id:
            messages.error(request, "Please select a template before converting.")
            return redirect('dashboard')

        template = services.get_template_by_id(template_id)
        if not template:
            messages.error(request, "Selected template is invalid.")
            return redirect('dashboard')
        template_content = template.get('content')

        if uploaded_file:
            # Check file size (limit to 5MB)
            if uploaded_file.size > 5 * 1024 * 1024:
                messages.error(request, "File size exceeds the 5MB limit.")
                return redirect('dashboard')

            title, _ = os.path.splitext(uploaded_file.name)

            # Save temporary file for Pandoc/Processing using tempfile to avoid collisions
            suffix = os.path.splitext(uploaded_file.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                for chunk in uploaded_file.chunks():
                    tmp_file.write(chunk)
                temp_path = tmp_file.name

            try:
                latex_code = services.convert_to_latex_ai(file_path=temp_path, template_content=template_content)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        elif content:
            if not template_content:
                messages.error(request, "Please select a template before converting.")
                return redirect('dashboard')
            latex_code = services.convert_to_latex_ai(content=content, template_content=template_content)
            # Try to extract a title from the content if it's long, else use default
            if len(content) > 20:
                title = content[:20].strip() + "..."
        else:
            messages.error(request, "No content provided for AI conversion.")
            return redirect('dashboard')

        if latex_code:
            project_id = services.create_project(
                owner_id=request.user.id,
                title=title,
                content=latex_code,
                filename="main.tex"
            )
            logger.info(f"User {request.user.id} created AI project: {project_id}")

            # Construct redirect URL with query parameter properly
            from django.urls import reverse
            url = reverse('editor_with_id', kwargs={'project_id': project_id})
            params = urlencode({'autocompile': 'true'})
            return redirect(f"{url}?{params}")
        else:
            messages.error(request, "AI conversion failed. Please try again or check your API key.")
            return redirect('dashboard')

    return redirect('dashboard')

@login_required
def upload_document(request):
    redirect_url = request.META.get('HTTP_REFERER', 'dashboard')
    if request.method == 'POST' and request.FILES.get('document'):
        uploaded_file = request.FILES['document']

        # Check file size (limit to 5MB)
        if uploaded_file.size > 5 * 1024 * 1024:
            messages.error(request, "File size exceeds the 5MB limit.")
            return redirect(redirect_url)

        allowed_extensions = ['.tex', '.md', '.markdown', '.docx', '.odt', '.html', '.txt']
        _, ext = os.path.splitext(uploaded_file.name.lower())
        if ext not in allowed_extensions:
            messages.error(request, f"File type {ext} not supported.")
            return redirect(redirect_url)

        try:
            title, _ = os.path.splitext(uploaded_file.name)
            filename = uploaded_file.name

            if ext == '.tex':
                content = uploaded_file.read().decode('utf-8')
            else:
                # Use a temporary file for pypandoc
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                    for chunk in uploaded_file.chunks():
                        tmp.write(chunk)
                    tmp_path = tmp.name

                try:
                    # Convert to LaTeX
                    content = pypandoc.convert_file(tmp_path, 'latex', extra_args=['--standalone'])
                    filename = title + '.tex'
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)

            project_id = services.create_project(
                owner_id=request.user.id,
                title=title,
                content=content,
                filename=filename
            )
            logger.info(f"User {request.user.id} uploaded document: {uploaded_file.name}")
            return redirect('editor_with_id', project_id=project_id)
        except Exception as e:
            logger.error(f"Error uploading document: {str(e)}")
            messages.error(request, "Failed to process the uploaded file.")
            return redirect(redirect_url)

    return redirect(redirect_url)

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
    templates = services.get_templates()
    notifications = services.get_user_notifications(request.user.id, limit=5)
    unread_count = services.get_unread_notification_count(request.user.id)
    api_keys = services.get_user_api_keys(request.user.id)

    context = {
        'projects': projects,
        'total_projects': total_projects,
        'recent_activity': recent_activity,
        'shared_projects': shared_projects_count,
        'templates': templates,
        'notifications': notifications,
        'unread_notification_count': unread_count,
        'api_keys': api_keys,
        'app_settings': services.get_all_settings(),
    }
    if request.GET.get('format') == 'json':
        return JsonResponse(context, safe=False)
    return render(request, 'pages/dashboardpage.html', context)

@login_required
def create_api_key_view(request):
    if request.method == 'POST':
        name = request.POST.get('name', 'Default Key')
        api_key = services.create_api_key(request.user.id, name)
        if api_key:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'api_key': {
                        'id': api_key['id'],
                        'key': api_key['key'],
                        'name': api_key['name']
                    }
                })
            messages.success(request, f"API Key created: {api_key['key']}")
            return redirect('dashboard')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': 'Failed to create API key'}, status=400)
            messages.error(request, 'Failed to create API key')
            return redirect('dashboard')
    return redirect('dashboard')

@login_required
def revoke_api_key_view(request, key_id):
    if request.method == 'POST':
        success = services.revoke_api_key(request.user.id, key_id)
        if success:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success'})
            messages.success(request, 'API key revoked successfully')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': 'API key not found'}, status=404)
            messages.error(request, 'API key not found')
    return redirect('dashboard')

@login_required
def mark_notification_read_view(request, notification_id):
    if request.method == 'POST':
        success = services.mark_notification_read(request.user.id, notification_id)
        if success:
            return JsonResponse({'status': 'success'})
        return JsonResponse({'status': 'error'}, status=404)
    return redirect('dashboard')

@login_required
def save_preferences_view(request):
    if request.method == 'POST':
        from .models import UserPreference
        prefs, created = UserPreference.objects.get_or_create(user=request.user)
        
        if 'dark_mode' in request.POST:
            prefs.dark_mode = request.POST.get('dark_mode') == 'true'
        if 'auto_compile' in request.POST:
            prefs.auto_compile = request.POST.get('auto_compile') == 'true'
        if 'font_size' in request.POST:
            prefs.font_size = request.POST.get('font_size')
        
        prefs.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        return redirect('settings')
    
    return redirect('settings')

@login_required
def create_version_view(request, project_id):
    if request.method == 'POST':
        from .models import Project, ProjectVersion
        try:
            project = Project.objects.get(id=project_id, owner=request.user)
            content = request.POST.get('content', project.content)
            message = request.POST.get('message', 'Auto-save version')
            
            last_version = ProjectVersion.objects.filter(project=project).order_by('-version_number').first()
            next_version = (last_version.version_number + 1) if last_version else 1
            
            ProjectVersion.objects.create(
                project=project,
                content=content,
                version_number=next_version,
                message=message,
                created_by=request.user
            )
            
            return JsonResponse({'status': 'success', 'version': next_version})
        except Project.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Project not found'}, status=404)
    return JsonResponse({'status': 'error'}, status=405)

@login_required
def get_versions_view(request, project_id):
    from .models import Project, ProjectVersion
    try:
        project = Project.objects.get(id=project_id, owner=request.user)
        versions = ProjectVersion.objects.filter(project=project).order_by('-version_number')
        
        return JsonResponse({
            'status': 'success',
            'versions': [{
                'version': v.version_number,
                'message': v.message,
                'created_at': v.created_at.isoformat(),
                'created_by': v.created_by.username if v.created_by else 'Unknown'
            } for v in versions]
        })
    except Project.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Project not found'}, status=404)

@login_required
def restore_version_view(request, project_id, version_number):
    from .models import Project, ProjectVersion
    if request.method == 'POST':
        try:
            project = Project.objects.get(id=project_id, owner=request.user)
            version = ProjectVersion.objects.get(project=project, version_number=version_number)
            
            project.content = version.content
            project.save()
            
            last_version = ProjectVersion.objects.filter(project=project).order_by('-version_number').first()
            next_version = (last_version.version_number + 1) if last_version else 1
            ProjectVersion.objects.create(
                project=project,
                content=version.content,
                version_number=next_version,
                message=f"Restored from version {version_number}",
                created_by=request.user
            )
            
            return JsonResponse({'status': 'success', 'content': version.content})
        except (Project.DoesNotExist, ProjectVersion.DoesNotExist):
            return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)
    return JsonResponse({'status': 'error'}, status=405)

@login_required
def create_share_invitation_view(request, project_id):
    if request.method == 'POST':
        from .models import Project, ShareInvitation
        import json
        
        try:
            project = Project.objects.get(id=project_id, owner=request.user)
            data = json.loads(request.body) if request.body else {}
            email = data.get('email', '').strip()
            permission = data.get('permission', 'read')
            
            if not email:
                return JsonResponse({'status': 'error', 'message': 'Email required'}, status=400)
            
            invitation = ShareInvitation.objects.create(
                project=project,
                inviter=request.user,
                invitee_email=email,
                permission=permission
            )
            
            services.create_notification(
                request.user.id,
                'Share Invitation Sent',
                f"Invitation sent to {email}",
                'success'
            )
            
            return JsonResponse({
                'status': 'success',
                'invitation': {
                    'id': str(invitation.id),
                    'email': invitation.invitee_email,
                    'permission': invitation.permission,
                    'status': invitation.status
                }
            })
        except Project.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Project not found'}, status=404)
    return JsonResponse({'status': 'error'}, status=405)

@login_required
def get_share_invitations_view(request, project_id):
    from .models import Project, ShareInvitation
    try:
        project = Project.objects.get(id=project_id, owner=request.user)
        invitations = ShareInvitation.objects.filter(project=project)
        collaborators = [{
            'id': str(c.id),
            'name': c.get_full_name() or c.username,
            'email': c.email,
            'permission': 'write'
        } for c in project.collaborators.all()]
        
        return JsonResponse({
            'status': 'success',
            'invitations': [{
                'id': str(i.id),
                'email': i.invitee_email,
                'permission': i.permission,
                'status': i.status,
                'created_at': i.created_at.isoformat()
            } for i in invitations],
            'collaborators': collaborators
        })
    except Project.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Project not found'}, status=404)

@login_required
def revoke_share_invitation_view(request, project_id, invitation_id):
    if request.method == 'POST':
        from .models import Project, ShareInvitation
        try:
            project = Project.objects.get(id=project_id, owner=request.user)
            invitation = ShareInvitation.objects.get(id=invitation_id, project=project)
            invitation.status = 'declined'
            invitation.save()
            return JsonResponse({'status': 'success'})
        except (Project.DoesNotExist, ShareInvitation.DoesNotExist):
            return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)
    return JsonResponse({'status': 'error'}, status=405)

@login_required
def remove_collaborator_view(request, project_id, user_id):
    if request.method == 'POST':
        from .models import Project, User
        try:
            project = Project.objects.get(id=project_id, owner=request.user)
            user = User.objects.get(id=user_id)
            project.collaborators.remove(user)
            return JsonResponse({'status': 'success'})
        except (Project.DoesNotExist, User.DoesNotExist):
            return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)
    return JsonResponse({'status': 'error'}, status=405)

@login_required
def reprocess_with_ai_view(request, project_id):
    if request.method == 'POST':
        from .models import Project, ProjectVersion
        try:
            project = Project.objects.get(id=project_id, owner=request.user)
            
            if request.FILES.get('document'):
                uploaded_file = request.FILES['document']
                
                last_version = ProjectVersion.objects.filter(project=project).order_by('-version_number').first()
                next_version = (last_version.version_number + 1) if last_version else 1
                ProjectVersion.objects.create(
                    project=project,
                    content=project.content,
                    version_number=next_version,
                    message="Before AI re-processing",
                    created_by=request.user
                )
                
                import tempfile
                import os
                
                suffix = os.path.splitext(uploaded_file.name)[1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                    for chunk in uploaded_file.chunks():
                        tmp_file.write(chunk)
                    temp_path = tmp_file.name
                
                try:
                    latex_code = services.convert_to_latex_ai(file_path=temp_path)
                    
                    if latex_code:
                        project.content = latex_code
                        project.save()
                        
                        services.create_notification(
                            request.user.id,
                            'AI Re-Processing Complete',
                            f"Project '{project.title}' has been re-processed with AI",
                            'success'
                        )
                        
                        return JsonResponse({
                            'status': 'success',
                            'content': latex_code,
                            'message': 'Document re-processed successfully'
                        })
                    else:
                        return JsonResponse({
                            'status': 'error',
                            'message': 'AI conversion failed. Please try again.'
                        }, status=400)
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No document uploaded'
                }, status=400)
                
        except Project.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Project not found'}, status=404)
    return JsonResponse({'status': 'error'}, status=405)

@login_required
def get_preferences_view(request):
    from .models import UserPreference
    prefs, created = UserPreference.objects.get_or_create(user=request.user)
    return JsonResponse({
        'status': 'success',
        'preferences': {
            'dark_mode': prefs.dark_mode,
            'auto_compile': prefs.auto_compile,
            'font_size': prefs.font_size,
            'editor_theme': prefs.editor_theme
        }
    })

@login_required
def upgrade_to_pro_view(request):
    context = {
        'app_settings': services.get_all_settings(),
        'user': request.user,
    }
    return render(request, 'pages/upgrade.html', context)

@login_required
def settings_page(request):
    from .models import UserPreference, Profile, APIKey
    
    prefs, created = UserPreference.objects.get_or_create(user=request.user)
    profile, _ = Profile.objects.get_or_create(user=request.user)
    api_keys = services.get_user_api_keys(request.user.id)
    
    context = {
        'profile': profile,
        'preferences': prefs,
        'api_keys': api_keys,
        'app_settings': services.get_all_settings(),
    }
    if request.GET.get('format') == 'json':
        return JsonResponse(context, safe=False)
    return render(request, 'pages/settings.html', context)

@login_required
def profile_page(request):
    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action', 'update')

        if action == 'update':
            user = request.user
            user.first_name = request.POST.get('first_name', '').strip()
            user.last_name = request.POST.get('last_name', '').strip()
            user.email = request.POST.get('email', '').strip()
            user.save()

            profile.bio = request.POST.get('bio', '').strip()
            profile.avatar_url = request.POST.get('avatar_url', '').strip()
            profile.affiliation = request.POST.get('affiliation', '').strip()
            profile.website = request.POST.get('website', '').strip()
            profile.github = request.POST.get('github', '').strip()
            profile.google_scholar = request.POST.get('google_scholar', '').strip()
            profile.save()

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success', 'message': 'Profile updated successfully'})
            messages.success(request, 'Profile updated successfully')
            return redirect('profile')

        elif action == 'change_password':
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')

            if not request.user.check_password(current_password):
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'message': 'Current password is incorrect'}, status=400)
                messages.error(request, 'Current password is incorrect')
            elif new_password != confirm_password:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'message': 'New passwords do not match'}, status=400)
                messages.error(request, 'New passwords do not match')
            elif len(new_password) < 8:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'message': 'Password must be at least 8 characters'}, status=400)
                messages.error(request, 'Password must be at least 8 characters')
            else:
                request.user.set_password(new_password)
                request.user.save()
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'success', 'message': 'Password changed successfully'})
                messages.success(request, 'Password changed successfully. Please log in again.')
                return redirect('login')

    context = {
        'profile': profile,
        'app_settings': services.get_all_settings(),
    }
    if request.GET.get('format') == 'json':
        return JsonResponse(context, safe=False)
    return render(request, 'pages/profile.html', context)

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
        # Always create a new project when "New Project" is clicked
        logger.info(f"Creating new project for user {request.user.id}")
        project_id = services.create_project(
            owner_id=request.user.id,
            title="Untitled Project",
            content="\\documentclass{article}\n\\begin{document}\n\n\\end{document}".replace('\\n', '\n')
        )
        return redirect('editor_with_id', project_id=project_id)

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

def pricing_page(request):
    context = {
        'app_settings': services.get_all_settings(),
    }
    if request.GET.get('format') == 'json':
        return JsonResponse(context, safe=False)
    return render(request, 'pages/pricing.html', context)

def documentation_page(request):
    context = {
        'app_settings': services.get_all_settings(),
    }
    if request.GET.get('format') == 'json':
        return JsonResponse(context, safe=False)
    return render(request, 'pages/documentation.html', context)

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
    filename = project.get('filename', 'main.tex')
    logger.info(f"Compiling project {project_id} for user {request.user.id}")

    try:
        # We use a POST request to the /data endpoint with the content as a file.
        # This avoids 414 Request-URI Too Large errors for long documents.
        # The /data endpoint expects a tarball or a single file and a 'target' parameter.
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w:gz') as tar:
            content_bytes = content.encode('utf-8')
            tar_info = tarfile.TarInfo(name=filename)
            tar_info.size = len(content_bytes)
            tar.addfile(tarinfo=tar_info, fileobj=io.BytesIO(content_bytes))

        tar_stream.seek(0)

        # The /data endpoint is usually at /data, not /compile
        compiler_url = settings.LATEX_COMPILER_URL.replace('/compile', '/data')

        response = httpx.post(
            compiler_url,
            params={"target": filename},
            files={"file": (f"{filename}.tar.gz", tar_stream, "application/gzip")},
            timeout=60.0
        )

        if response.status_code == 200:
            logger.info(f"Compilation successful for project {project_id}")
            pdf_response = HttpResponse(response.content, content_type='application/pdf')
            pdf_response['Content-Disposition'] = f'inline; filename="{filename.replace(".tex", ".pdf")}"'
            return pdf_response
        else:
            # On failure, LaTeX.Online often returns the log in the body
            logger.error(f"Compilation failed for project {project_id}: {response.text[:100]}...")
            return HttpResponse(f"Compilation failed:\n\n{response.text}", content_type="text/plain", status=400)
    except httpx.RequestError as e:
        logger.error(f"Error connecting to LaTeX.Online for project {project_id}: {str(e)}")
        return HttpResponse("LaTeX compilation service is not available. Please ensure Docker is running with: docker-compose up -d", status=503)

def handler404(request, exception):
    return render(request, '404.html', status=404)

def handler500(request):
    return render(request, '500.html', status=500)
