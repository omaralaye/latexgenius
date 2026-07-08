from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.template.defaultfilters import urlencode as urlencode_filter
from . import services
from .models import Profile, ConversionJob, Project, ProjectVersion, ShareInvitation
from .validation import (
    SignupSchema, ProfileUpdateSchema, PasswordChangeSchema,
    AIConvertSchema, SavePreferencesSchema, CreateVersionSchema,
    ShareInvitationSchema, SaveProjectSchema, CheckoutSessionSchema,
    validate_file_extension
)
from pydantic import ValidationError
from datetime import datetime
import httpx
import logging
import io
import tarfile
import pypandoc
import os
import tempfile
import shutil
import threading
import json
from urllib.parse import urlencode

User = get_user_model()
logger = logging.getLogger('myapp')

PERMISSION_LEVELS = {
    'read': 10,
    'write': 20,
    'admin': 30,
    'owner': 40,
}

def _get_project_with_permission(user, project_id, required='read'):
    try:
        project = Project.objects.get(id=project_id)
    except (Project.DoesNotExist, ValueError):
        return None

    if project.owner_id == user.id:
        return project

    if project.collaborators.filter(id=user.id).exists():
        invitation = ShareInvitation.objects.filter(
            project=project,
            invitee=user,
            status='accepted'
        ).first()
        collaborator_perm = invitation.permission if invitation else 'read'
        if PERMISSION_LEVELS.get(collaborator_perm, 0) >= PERMISSION_LEVELS.get(required, 0):
            return project

    return None

@login_required
def conversion_page(request, project_id):
    project = _get_project_with_permission(request.user, project_id, 'read')
    if not project:
        messages.error(request, "Project not found or access denied.")
        return redirect('dashboard')
    try:
        job = ConversionJob.objects.filter(project=project).latest('created_at')
    except ConversionJob.DoesNotExist:
        messages.error(request, "No conversion job found for this project.")
        return redirect('dashboard')
    context = {
        'project_id': project_id,
        'job_id': job.id,
    }
    return render(request, 'pages/conversion.html', context)

@login_required
def conversion_status_json(request, project_id):
    project = _get_project_with_permission(request.user, project_id, 'read')
    if not project:
        return JsonResponse({'status': 'error', 'message': 'Project not found'}, status=404)
    try:
        job = ConversionJob.objects.filter(project=project).latest('created_at')
        return JsonResponse({
            'status': job.status,
            'progress_message': job.progress_message,
            'progress_percent': job.progress_percent,
            'error_message': job.error_message,
            'project_id': project_id,
        })
    except ConversionJob.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'No conversion job found'}, status=404)

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

def signup_page(request):
    if request.method == 'POST':
        try:
            data = SignupSchema(
                email=request.POST.get('email', ''),
                password=request.POST.get('password', ''),
                name=request.POST.get('name', ''),
            )
        except ValidationError as e:
            errors = '; '.join(e.errors())
            logger.warning(f"Signup validation failed: {errors}")
            if request.GET.get('format') == 'json':
                return JsonResponse({"status": "error", "message": errors}, status=400)
            messages.error(request, errors)
            return render(request, 'pages/signup.html')

        username = data.email
        email = data.email
        password = data.password
        first_name = data.name

        if User.objects.filter(username=username).exists():
            logger.warning(f"Signup failed: User already exists: {username}")
            if request.GET.get('format') == 'json':
                return JsonResponse({"status": "error", "message": "User already exists."}, status=400)
            messages.error(request, "User already exists.")
        else:
            user = User.objects.create_user(username=username, email=email, password=password, first_name=first_name)
            user.backend = 'django.contrib.auth.backends.ModelBackend'
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
        is_pro = services.user_is_pro(request.user.id)
        conversion_count = ConversionJob.objects.filter(project__owner=request.user).count()
        if not is_pro and conversion_count >= 5:
            messages.error(request, "You've reached the limit of 5 free AI conversions. Upgrade to Pro for unlimited conversions.")
            return redirect('upgrade')

        content = request.POST.get('content')
        uploaded_file = request.FILES.get('document')

        try:
            validated = AIConvertSchema(
                content=content or '',
                template_id=request.POST.get('template_id', ''),
            )
        except ValidationError as e:
            errors = '; '.join(e.errors())
            messages.error(request, errors)
            return redirect('dashboard')

        template = services.get_template_by_id(validated.template_id)
        if not template:
            messages.error(request, "Selected template is invalid.")
            return redirect('dashboard')
        template_content = template.get('content')

        project_id = services.create_project(
            owner_id=request.user.id,
            title="AI Project",
            content="",
            filename="main.tex"
        )
        project = Project.objects.get(id=project_id)
        job = ConversionJob.objects.create(
            project=project,
            status='pending',
            progress_message='Preparing conversion...',
            progress_percent=0
        )
        logger.info(f"User {request.user.id} created AI project {project_id} with conversion job {job.id}")

        if uploaded_file:
            if uploaded_file.size > 5 * 1024 * 1024:
                job.status = 'failed'
                job.progress_message = 'File size exceeds the 5MB limit.'
                job.save()
                messages.error(request, "File size exceeds the 5MB limit.")
                return redirect('dashboard')

            if not validate_file_extension(uploaded_file.name):
                job.status = 'failed'
                job.progress_message = f'File type not supported.'
                job.save()
                messages.error(request, f"File type not supported.")
                return redirect('dashboard')

            title, _ = os.path.splitext(uploaded_file.name)
            Project.objects.filter(id=project_id).update(title=title)

            suffix = os.path.splitext(uploaded_file.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                for chunk in uploaded_file.chunks():
                    tmp_file.write(chunk)
                temp_path = tmp_file.name

            t = threading.Thread(
                target=services.run_conversion_job,
                args=(job.id, project_id, temp_path, None, template_content, True),
                daemon=True
            )
            t.start()
        elif validated.content:
            content = validated.content
            if len(content) > 20:
                title = content[:20].strip() + "..."
                Project.objects.filter(id=project_id).update(title=title)

            t = threading.Thread(
                target=services.run_conversion_job,
                args=(job.id, project_id, None, content, template_content, False),
                daemon=True
            )
            t.start()
        else:
            job.status = 'failed'
            job.progress_message = 'No content provided for AI conversion.'
            job.save()
            messages.error(request, "No content provided for AI conversion.")
            return redirect('dashboard')

        return redirect('conversion_page', project_id=project_id)

    return redirect('dashboard')

@login_required
def upload_document(request):
    redirect_url = request.META.get('HTTP_REFERER', 'dashboard')
    if request.method == 'POST' and request.FILES.get('document'):
        uploaded_file = request.FILES['document']

        if uploaded_file.size > 5 * 1024 * 1024:
            messages.error(request, "File size exceeds the 5MB limit.")
            return redirect(redirect_url)

        if not validate_file_extension(uploaded_file.name):
            _, ext = os.path.splitext(uploaded_file.name.lower())
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
    services.ensure_default_subscription(request.user)
    user_sub = services.get_user_subscription(request.user.id)
    context = {
        'projects': projects,
        'total_projects': total_projects,
        'recent_activity': recent_activity,
        'shared_projects': shared_projects_count,
        'templates': templates,
        'notifications': notifications,
        'unread_notification_count': unread_count,
        'app_settings': services.get_all_settings(),
        'user_subscription': user_sub,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
    }
    if request.GET.get('format') == 'json':
        return JsonResponse(context, safe=False)
    return render(request, 'pages/dashboardpage.html', context)

@login_required
def mark_notification_read_view(request, notification_id):
    if request.method == 'POST':
        success = services.mark_notification_read(request.user.id, notification_id)
        if success:
            return JsonResponse({'status': 'success'})
        return JsonResponse({'status': 'error'}, status=404)
    return redirect('dashboard')

@login_required
def notifications_page(request):
    notifications = services.get_user_notifications(request.user.id, limit=None)
    unread_count = services.get_unread_notification_count(request.user.id)
    recent_notifications = services.get_user_notifications(request.user.id, limit=5)
    context = {
        'notifications': notifications,
        'unread_notification_count': unread_count,
        'recent_notifications': recent_notifications,
    }
    if request.GET.get('format') == 'json':
        return JsonResponse(context, safe=False)
    return render(request, 'pages/notifications.html', context)

@login_required
def mark_all_notifications_read_view(request):
    if request.method == 'POST':
        success = services.mark_all_notifications_read(request.user.id)
        if success:
            return JsonResponse({'status': 'success'})
        return JsonResponse({'status': 'error'}, status=500)
    return redirect('notifications')

@login_required
def save_preferences_view(request):
    if request.method == 'POST':
        from .models import UserPreference

        try:
            validated = SavePreferencesSchema(
                dark_mode=request.POST.get('dark_mode') == 'true' if 'dark_mode' in request.POST else None,
                auto_compile=request.POST.get('auto_compile') == 'true' if 'auto_compile' in request.POST else None,
                font_size=request.POST.get('font_size') if 'font_size' in request.POST else None,
            )
        except ValidationError as e:
            return JsonResponse({'status': 'error', 'message': '; '.join(e.errors())}, status=400)

        prefs, created = UserPreference.objects.get_or_create(user=request.user)

        if validated.dark_mode is not None:
            prefs.dark_mode = validated.dark_mode
        if validated.auto_compile is not None:
            prefs.auto_compile = validated.auto_compile
        if validated.font_size is not None:
            prefs.font_size = validated.font_size

        prefs.save()
        return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error'}, status=405)

@login_required
def create_version_view(request, project_id):
    if request.method == 'POST':
        from .models import ProjectVersion
        project = _get_project_with_permission(request.user, project_id, 'write')
        if not project:
            return JsonResponse({'status': 'error', 'message': 'Project not found'}, status=404)

        try:
            validated = CreateVersionSchema(
                content=request.POST.get('content', project.content),
                message=request.POST.get('message', 'Auto-save version'),
            )
        except ValidationError as e:
            return JsonResponse({'status': 'error', 'message': '; '.join(e.errors())}, status=400)

        last_version = ProjectVersion.objects.filter(project=project).order_by('-version_number').first()
        next_version = (last_version.version_number + 1) if last_version else 1

        ProjectVersion.objects.create(
            project=project,
            content=validated.content,
            version_number=next_version,
            message=validated.message,
            created_by=request.user
        )

        return JsonResponse({'status': 'success', 'version': next_version})
    return JsonResponse({'status': 'error'}, status=405)

@login_required
def get_versions_view(request, project_id):
    from .models import ProjectVersion
    project = _get_project_with_permission(request.user, project_id, 'read')
    if not project:
        return JsonResponse({'status': 'error', 'message': 'Project not found'}, status=404)
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

@login_required
def restore_version_view(request, project_id, version_number):
    from .models import ProjectVersion
    if request.method == 'POST':
        project = _get_project_with_permission(request.user, project_id, 'write')
        if not project:
            return JsonResponse({'status': 'error', 'message': 'Project not found'}, status=404)
        try:
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
        except ProjectVersion.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)
    return JsonResponse({'status': 'error'}, status=405)

@login_required
def create_share_invitation_view(request, project_id):
    if request.method == 'POST':
        from .models import ShareInvitation
        import json

        project = _get_project_with_permission(request.user, project_id, 'admin')
        if not project:
            return JsonResponse({'status': 'error', 'message': 'Project not found'}, status=404)
        data = json.loads(request.body) if request.body else {}

        try:
            validated = ShareInvitationSchema(
                email=data.get('email', ''),
                permission=data.get('permission', 'read'),
            )
        except ValidationError as e:
            return JsonResponse({'status': 'error', 'message': '; '.join(e.errors())}, status=400)

        invitation = ShareInvitation.objects.create(
            project=project,
            inviter=request.user,
            invitee_email=validated.email,
            permission=validated.permission
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
    return JsonResponse({'status': 'error'}, status=405)

@login_required
def get_share_invitations_view(request, project_id):
    from .models import ShareInvitation
    project = _get_project_with_permission(request.user, project_id, 'read')
    if not project:
        return JsonResponse({'status': 'error', 'message': 'Project not found'}, status=404)
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

@login_required
def revoke_share_invitation_view(request, project_id, invitation_id):
    if request.method == 'POST':
        from .models import ShareInvitation
        project = _get_project_with_permission(request.user, project_id, 'admin')
        if not project:
            return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)
        try:
            invitation = ShareInvitation.objects.get(id=invitation_id, project=project)
            invitation.status = 'declined'
            invitation.save()
            return JsonResponse({'status': 'success'})
        except ShareInvitation.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)
    return JsonResponse({'status': 'error'}, status=405)

@login_required
def remove_collaborator_view(request, project_id, user_id):
    if request.method == 'POST':
        from .models import User
        project = _get_project_with_permission(request.user, project_id, 'admin')
        if not project:
            return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)
        try:
            user = User.objects.get(id=user_id)
            project.collaborators.remove(user)
            return JsonResponse({'status': 'success'})
        except User.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)
    return JsonResponse({'status': 'error'}, status=405)

@login_required
def delete_project_view(request, project_id):
    if request.method == 'POST':
        project = _get_project_with_permission(request.user, project_id, 'owner')
        if not project:
            return JsonResponse({'status': 'error', 'message': 'Project not found'}, status=404)
        services.delete_project(project_id)
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=405)

@login_required
def reprocess_with_ai_view(request, project_id):
    if request.method == 'POST':
        project = _get_project_with_permission(request.user, project_id, 'write')
        if not project:
            return JsonResponse({'status': 'error', 'message': 'Project not found'}, status=404)

        if request.FILES.get('document'):
            uploaded_file = request.FILES['document']

            if uploaded_file.size > 5 * 1024 * 1024:
                return JsonResponse({'status': 'error', 'message': 'File size exceeds the 5MB limit.'}, status=400)

            if not validate_file_extension(uploaded_file.name):
                return JsonResponse({'status': 'error', 'message': 'File type not supported.'}, status=400)

            ProjectVersion.objects.create(
                project=project,
                content=project.content,
                version_number=(ProjectVersion.objects.filter(project=project).order_by('-version_number').first().version_number + 1) if ProjectVersion.objects.filter(project=project).exists() else 1,
                message="Before AI re-processing",
                created_by=request.user
            )

            suffix = os.path.splitext(uploaded_file.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                for chunk in uploaded_file.chunks():
                    tmp_file.write(chunk)
                temp_path = tmp_file.name

            job = ConversionJob.objects.create(
                project=project,
                status='pending',
                progress_message='Reprocessing document with Kimi K2.6...',
                progress_percent=0
            )

            t = threading.Thread(
                target=services.run_conversion_job,
                args=(job.id, project_id, temp_path, None, None, True),
                daemon=True
            )
            t.start()

            return JsonResponse({
                'status': 'started',
                'job_id': job.id,
                'project_id': project_id,
                'message': 'AI re-processing started'
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'No document uploaded'
            }, status=400)
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
    services.ensure_default_subscription(request.user)
    plans = services.get_subscription_plans()
    user_sub = services.get_user_subscription(request.user.id)
    context = {
        'app_settings': services.get_all_settings(),
        'user': request.user,
        'plans': plans,
        'user_subscription': user_sub,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
    }
    return render(request, 'pages/upgrade.html', context)

@login_required
def settings_page(request):
    from .models import UserPreference, Profile
    
    prefs, created = UserPreference.objects.get_or_create(user=request.user)
    profile, _ = Profile.objects.get_or_create(user=request.user)
    notifications = services.get_user_notifications(request.user.id, limit=5)
    unread_count = services.get_unread_notification_count(request.user.id)
    
    context = {
        'profile': profile,
        'preferences': prefs,
        'notifications': notifications,
        'unread_notification_count': unread_count,
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
            try:
                validated = ProfileUpdateSchema(
                    first_name=request.POST.get('first_name', ''),
                    last_name=request.POST.get('last_name', ''),
                    email=request.POST.get('email', ''),
                    bio=request.POST.get('bio', ''),
                    avatar_url=request.POST.get('avatar_url', ''),
                    affiliation=request.POST.get('affiliation', ''),
                    website=request.POST.get('website', ''),
                    github=request.POST.get('github', ''),
                    google_scholar=request.POST.get('google_scholar', ''),
                )
            except ValidationError as e:
                errors = '; '.join(e.errors())
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'message': errors}, status=400)
                messages.error(request, errors)
                return redirect('profile')

            user = request.user
            user.first_name = validated.first_name
            user.last_name = validated.last_name
            user.email = validated.email
            user.save()

            profile.bio = validated.bio
            profile.avatar_url = validated.avatar_url
            profile.affiliation = validated.affiliation
            profile.website = validated.website
            profile.github = validated.github
            profile.google_scholar = validated.google_scholar
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
            else:
                try:
                    PasswordChangeSchema(
                        current_password=current_password,
                        new_password=new_password,
                        confirm_password=confirm_password,
                    )
                except ValidationError as e:
                    errors = '; '.join(e.errors())
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'status': 'error', 'message': errors}, status=400)
                    messages.error(request, errors)
                    return redirect('profile')

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
        project = _get_project_with_permission(request.user, project_id, 'read')
        if not project:
            logger.warning(f"Unauthorized access attempt to project {project_id} by user {request.user.id}")
            return JsonResponse({"status": "error", "message": "Project not found or access denied."}, status=404)
    else:
        template_id = request.GET.get('template_id')
        if template_id:
            template = services.get_template_by_id(template_id)
            if template:
                title = template['name']
                content = template['content']
            else:
                title = "Untitled Project"
                content = "\\documentclass{article}\n\\begin{document}\n\n\\end{document}".replace('\\n', '\n')
        else:
            title = "Untitled Project"
            content = "\\documentclass{article}\n\\begin{document}\n\n\\end{document}".replace('\\n', '\n')

        logger.info(f"Creating new project for user {request.user.id}")
        project_id = services.create_project(
            owner_id=request.user.id,
            title=title,
            content=content
        )
        return redirect('editor_with_id', project_id=project_id)

    from .models import UserPreference
    prefs = UserPreference.objects.filter(user=request.user).first()
    context = {
        'project': project,
        'preferences': prefs,
        'preferences_json': json.dumps({
            'dark_mode': prefs.dark_mode if prefs else False,
            'auto_compile': prefs.auto_compile if prefs else True,
            'font_size': prefs.font_size if prefs else '14px',
            'editor_theme': prefs.editor_theme if prefs else 'default',
        }) if prefs else '{}',
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

def features_page(request):
    features = services.get_features()
    context = {
        'features': features,
        'app_settings': services.get_all_settings(),
    }
    if request.GET.get('format') == 'json':
        return JsonResponse(context, safe=False)
    return render(request, 'pages/features.html', context)

def pricing_page(request):
    plans = services.get_subscription_plans()
    user_sub = None
    if request.user.is_authenticated:
        services.ensure_default_subscription(request.user)
        user_sub = services.get_user_subscription(request.user.id)
    context = {
        'app_settings': services.get_all_settings(),
        'plans': plans,
        'user_subscription': user_sub,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
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

@login_required
def save_project(request, project_id):
    project = _get_project_with_permission(request.user, project_id, 'write')
    if not project:
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

        try:
            validated = SaveProjectSchema(content=content, title=title)
        except ValidationError as e:
            return JsonResponse({'status': 'error', 'message': '; '.join(e.errors())}, status=400)

        update_data = {}
        if validated.content is not None:
            update_data['content'] = validated.content
        if validated.title is not None:
            update_data['title'] = validated.title

        if update_data:
            logger.info(f"Saving project {project_id} for user {request.user.id}")
            services.update_project(project_id, update_data)
            return JsonResponse({"status": "success"})

    return JsonResponse({"status": "error", "message": "Invalid request method"}, status=405)

@login_required
def compile_project(request, project_id):
    project = _get_project_with_permission(request.user, project_id, 'write')
    if not project:
        logger.warning(f"Unauthorized compilation attempt for project {project_id} by user {request.user.id}")
        return HttpResponse("Project not found or access denied.", status=404)

    content = project.content
    filename = project.filename
    logger.info(f"Compiling project {project_id} for user {request.user.id}")

    # Try latex-online service first, fall back to Docker-based direct compilation
    try:
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w:gz') as tar:
            content_bytes = content.encode('utf-8')
            tar_info = tarfile.TarInfo(name=filename)
            tar_info.size = len(content_bytes)
            tar.addfile(tarinfo=tar_info, fileobj=io.BytesIO(content_bytes))
        tar_stream.seek(0)

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
            logger.error(f"Compilation failed for project {project_id}: {response.text[:100]}...")
            return HttpResponse(f"Compilation failed:\n\n{response.text}", content_type="text/plain", status=400)
    except httpx.RequestError:
        logger.warning(f"latex-online service unavailable for project {project_id}, trying Docker direct compilation...")

    # Fallback: compile directly via Docker using the latex-online image's texlive
    import subprocess
    import shutil
    tmp_dir = tempfile.mkdtemp(prefix="latex_")
    tex_path = os.path.join(tmp_dir, filename)
    try:
        with open(tex_path, 'w', encoding='utf-8') as f:
            f.write(content)

        docker_cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "-v", f"{tmp_dir}:/data",
            "--entrypoint", "",
            "-w", "/data",
            "aslushnikov/latex-online",
            "pdflatex", "-interaction=nonstopmode", filename
        ]
        result = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=120
        )
        logger.info(f"Docker pdflatex exited with code {result.returncode}")

        pdf_path = os.path.join(tmp_dir, filename.replace('.tex', '.pdf'))
        if os.path.exists(pdf_path):
            with open(pdf_path, 'rb') as f:
                pdf_content = f.read()
            logger.info(f"Docker compilation successful for project {project_id}")
            pdf_response = HttpResponse(pdf_content, content_type='application/pdf')
            pdf_response['Content-Disposition'] = f'inline; filename="{filename.replace(".tex", ".pdf")}"'
            return pdf_response

        # pdflatex might need multiple passes; try second pass
        result = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=120)
        if os.path.exists(pdf_path):
            with open(pdf_path, 'rb') as f:
                pdf_content = f.read()
            logger.info(f"Docker compilation (pass 2) successful for project {project_id}")
            pdf_response = HttpResponse(pdf_content, content_type='application/pdf')
            pdf_response['Content-Disposition'] = f'inline; filename="{filename.replace(".tex", ".pdf")}"'
            return pdf_response

        log_path = os.path.join(tmp_dir, filename.replace('.tex', '.log'))
        log_text = ""
        if os.path.exists(log_path):
            with open(log_path, 'r', errors='ignore') as f:
                log_text = f.read()[-2000:]
        logger.error(f"Docker pdflatex failed for project {project_id}")
        return HttpResponse(f"LaTeX compilation error:\n\n{log_text}", content_type="text/plain", status=400)
    except subprocess.TimeoutExpired:
        logger.error(f"Docker pdflatex timed out for project {project_id}")
        return HttpResponse("LaTeX compilation timed out.", status=503)
    except FileNotFoundError:
        logger.error("Docker is not available for direct compilation")
        return HttpResponse("LaTeX compilation service is not available. Please ensure Docker is running.", status=503)
    except Exception as e:
        logger.error(f"Docker compilation error for project {project_id}: {str(e)}")
        return HttpResponse(f"LaTeX compilation error: {str(e)}", status=500)
    finally:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)

@login_required
def create_checkout_session_view(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = request.POST.dict()

    try:
        validated = CheckoutSessionSchema(price_id=data.get('price_id', ''))
    except ValidationError as e:
        return JsonResponse({'status': 'error', 'message': '; '.join(e.errors())}, status=400)

    success_url = request.build_absolute_uri('/payment/success/')
    cancel_url = request.build_absolute_uri('/payment/cancel/')

    result = services.create_stripe_checkout_session(
        user_id=request.user.id,
        price_id=validated.price_id,
        success_url=success_url,
        cancel_url=cancel_url,
    )

    if result:
        return JsonResponse({'status': 'success', 'url': result['url']})
    return JsonResponse({'status': 'error', 'message': 'Failed to create checkout session'}, status=500)


@csrf_exempt
def stripe_webhook_view(request):
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    event_type = event.get('type')

    if event_type == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session.get('metadata', {}).get('user_id')
        customer_id = session.get('customer')
        subscription_id = session.get('subscription')

        if user_id:
            from .models import UserSubscription
            sub = UserSubscription.objects.filter(user_id=user_id).first()
            if sub:
                sub.stripe_customer_id = customer_id
                sub.stripe_subscription_id = subscription_id
                sub.save()

            if subscription_id:
                try:
                    stripe_sub = stripe.subscriptions.retrieve(subscription_id)
                    services.update_subscription_from_stripe(stripe_sub)
                except Exception as e:
                    logger.error(f"Failed to retrieve subscription: {e}")

    elif event_type == 'invoice.paid':
        invoice = event['data']['object']
        subscription_id = invoice.get('subscription')
        customer_id = invoice.get('customer')

        if subscription_id:
            try:
                stripe_sub = stripe.subscriptions.retrieve(subscription_id)
                services.update_subscription_from_stripe(stripe_sub)
            except Exception as e:
                logger.error(f"Failed to update subscription from invoice: {e}")

    elif event_type == 'customer.subscription.updated':
        stripe_subscription = event['data']['object']
        services.update_subscription_from_stripe(stripe_subscription)

    elif event_type == 'customer.subscription.deleted':
        stripe_subscription = event['data']['object']
        sub = services.update_subscription_from_stripe(stripe_subscription)
        if sub:
            from .models import SubscriptionPlan
            free_plan = SubscriptionPlan.objects.filter(name__iexact='free').first()
            sub.plan = free_plan
            sub.status = 'canceled'
            sub.save()

    return HttpResponse(status=200)


@login_required
def customer_portal_view(request):
    return_url = request.build_absolute_uri('/settings/')
    result = services.create_stripe_customer_portal_session(
        user_id=request.user.id,
        return_url=return_url,
    )

    if result:
        return redirect(result['url'])
    messages.error(request, 'No active subscription found.')
    return redirect('settings')


@login_required
def subscription_success_view(request):
    services.ensure_default_subscription(request.user)
    sub = services.get_user_subscription(request.user.id)
    messages.success(request, 'Subscription successful! Welcome to Pro.')
    return render(request, 'pages/subscription_success.html', {
        'subscription': sub,
        'app_settings': services.get_all_settings(),
    })


@login_required
def subscription_cancel_view(request):
    services.ensure_default_subscription(request.user)
    messages.info(request, 'Subscription canceled. You can upgrade again anytime.')
    return render(request, 'pages/subscription_cancel.html', {
        'app_settings': services.get_all_settings(),
    })


def privacy_page(request):
    return render(request, 'pages/privacy.html', {
        'app_settings': services.get_all_settings(),
    })

def terms_page(request):
    return render(request, 'pages/terms.html', {
        'app_settings': services.get_all_settings(),
    })

def contact_page(request):
    return render(request, 'pages/contact.html', {
        'app_settings': services.get_all_settings(),
    })

def handler404(request, exception):
    return render(request, '404.html', status=404)

def handler500(request):
    return render(request, '500.html', status=500)
