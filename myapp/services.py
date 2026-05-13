from datetime import datetime
from django.utils import timezone
from django.conf import settings
from .models import Project, Template, AppSetting, Feature, Statistic, Testimonial, APIKey, Notification
from django.contrib.auth.models import User
import logging
import openai
import pypandoc
import os

logger = logging.getLogger('myapp')

def serialize_project(project):
    if project is None or not project.id:
        return None
    return {
        "id": str(project.id),
        "owner_id": project.owner_id,
        "title": project.title,
        "content": project.content,
        "filename": project.filename,
        "status": project.status,
        "last_modified": project.last_modified,
        "collaborator_ids": [u.id for u in project.collaborators.all()]
    }

def serialize_template(template):
    if template is None:
        return None
    return {
        "id": str(template.id),
        "name": template.name,
        "category": template.category,
        "image_url": template.image_url,
        "content": template.content
    }

def serialize_feature(feature):
    return {
        "id": str(feature.id),
        "title": feature.title,
        "description": feature.description,
        "icon": feature.icon,
        "order": feature.order
    }

def serialize_statistic(stat):
    return {
        "id": str(stat.id),
        "label": stat.label,
        "value": stat.value,
        "description": stat.description,
        "order": stat.order
    }

def serialize_testimonial(testimonial):
    return {
        "id": str(testimonial.id),
        "name": testimonial.name,
        "role": testimonial.role,
        "quote": testimonial.quote,
        "image_url": testimonial.image_url
    }

# Projects CRUD
def create_project(owner_id, title, content, filename='main.tex', status='draft'):
    user = User.objects.get(id=owner_id)
    project = Project.objects.create(
        owner=user,
        title=title,
        content=content,
        filename=filename,
        status=status
    )
    return str(project.id)

def get_projects(filter_query=None, sort=None, limit=None):
    queryset = Project.objects.all().prefetch_related('collaborators')
    if filter_query:
        # Compatibility with the previous dict-based filter_query used by MongoDB
        # Views currently use: get_projects({"owner_id": owner_id}, sort=[("last_modified", -1)])
        # which translates well to Django's .filter(**{"owner_id": owner_id})
        queryset = queryset.filter(**filter_query)
    if sort:
        sort_args = []
        for field, direction in sort:
            prefix = '-' if direction == -1 else ''
            sort_args.append(f"{prefix}{field}")
        queryset = queryset.order_by(*sort_args)
    if limit:
        queryset = queryset[:limit]
    return [serialized for p in queryset if (serialized := serialize_project(p))]

def get_user_projects(owner_id):
    return get_projects({"owner_id": owner_id}, sort=[("last_modified", -1)])

def get_shared_projects_count(user_id):
    return Project.objects.filter(collaborators__id=user_id).count()

def get_project_by_id(project_id):
    try:
        project = Project.objects.prefetch_related('collaborators').get(id=project_id)
        return serialize_project(project)
    except (Project.DoesNotExist, ValueError):
        return None

def update_project(project_id, update_data):
    try:
        project = Project.objects.get(id=project_id)

        collaborator_ids = update_data.pop('collaborator_ids', None)

        for key, value in update_data.items():
            setattr(project, key, value)

        # Explicitly update last_modified just in case, though auto_now=True handles it on save()
        project.last_modified = timezone.now()
        project.save()

        if collaborator_ids is not None:
            project.collaborators.set(User.objects.filter(id__in=collaborator_ids))
    except Project.DoesNotExist:
        logger.error(f"Failed to update project: Project {project_id} does not exist.")
    except ValueError as e:
        logger.error(f"Failed to update project {project_id} due to value error: {str(e)}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while updating project {project_id}: {str(e)}")

def delete_project(project_id):
    try:
        Project.objects.filter(id=project_id).delete()
        logger.info(f"Project {project_id} deleted.")
    except ValueError as e:
        logger.error(f"Failed to delete project {project_id} due to value error: {str(e)}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while deleting project {project_id}: {str(e)}")

# Templates
def get_templates(limit=None):
    queryset = Template.objects.all()
    if limit:
        queryset = queryset[:limit]
    return [serialize_template(t) for t in queryset]

def get_template_by_id(template_id):
    try:
        template = Template.objects.get(id=template_id)
        return serialize_template(template)
    except (Template.DoesNotExist, ValueError):
        return None

# Settings
def get_all_settings():
    try:
        settings = {s.key: s.value for s in AppSetting.objects.all()}
        return settings
    except Exception as e:
        logger.error(f"Error fetching settings: {e}")
        return {}

# Features
def get_features():
    return [serialize_feature(f) for f in Feature.objects.all().order_by('order')]

# Statistics
def get_statistics():
    return [serialize_statistic(s) for s in Statistic.objects.all().order_by('order')]

# Testimonials
def get_testimonials():
    return [serialize_testimonial(t) for t in Testimonial.objects.all()]

# AI Conversion
def convert_to_latex_ai(content=None, file_path=None, template_content=None):
    """
    Converts document content or a file to LaTeX using OpenAI, optionally respecting a selected template.
    """
    input_text = ""
    if file_path:
        try:
            # Try to convert to markdown first as it's a good intermediate format for LLMs
            input_text = pypandoc.convert_file(file_path, 'markdown')
        except Exception as e:
            logger.error(f"Pandoc conversion failed: {e}")
            # Fallback to reading as text
            try:
                with open(file_path, 'r', errors='ignore') as f:
                    input_text = f.read()
            except Exception as read_err:
                logger.error(f"Failed to read file: {read_err}")
                return None
    else:
        input_text = content

    if not input_text:
        logger.warning("AI conversion attempted with empty input.")
        return None

    if not settings.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is not configured.")
        return None

    try:
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

        prompt = "Convert the following document into a high-quality, valid LaTeX document. Return ONLY the LaTeX code, starting from \\documentclass and ending with \\end{document}."
        if template_content:
            prompt += "\n\nUse the provided LaTeX template as the formatting and structure guide. Preserve the template style and incorporate the document content into that template."
            prompt += f"\n\nTemplate Content:\n{template_content}"
        prompt += f"\n\nDocument Content:\n{input_text}"

        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a LaTeX expert. Your task is to convert any provided document into a clean, well-structured LaTeX source code in accordance with the requested template."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )

        latex_code = response.choices[0].message.content

        # Clean up Markdown code blocks if present
        if "```latex" in latex_code:
            latex_code = latex_code.split("```latex")[1].split("```")[0]
        elif "```" in latex_code:
            latex_code = latex_code.split("```")[1].split("```")[0]

        return latex_code.strip()
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return None

import secrets
import hashlib

def generate_api_key():
    return "lg_" + secrets.token_urlsafe(48)

def hash_api_key(key):
    return hashlib.sha256(key.encode()).hexdigest()

def create_api_key(user_id, name="Default Key"):
    from django.contrib.auth.models import User
    try:
        user = User.objects.get(id=user_id)
        raw_key = generate_api_key()
        hashed_key = hash_api_key(raw_key)
        api_key = APIKey.objects.create(
            user=user,
            key=hashed_key,
            name=name,
            is_active=True
        )
        return {
            "id": str(api_key.id),
            "key": raw_key,
            "name": api_key.name,
            "created_at": api_key.created_at,
        }
    except Exception as e:
        logger.error(f"Failed to create API key: {e}")
        return None

def get_user_api_keys(user_id):
    from django.contrib.auth.models import User
    try:
        keys = APIKey.objects.filter(user_id=user_id).order_by('-created_at')
        return [{
            "id": str(k.id),
            "name": k.name,
            "key_prefix": k.key[:8] + "...",
            "is_active": k.is_active,
            "created_at": k.created_at,
            "last_used_at": k.last_used_at,
            "usage_count": k.usage_count,
        } for k in keys]
    except Exception as e:
        logger.error(f"Failed to get API keys: {e}")
        return []

def revoke_api_key(user_id, key_id):
    try:
        api_key = APIKey.objects.get(id=key_id, user_id=user_id)
        api_key.is_active = False
        api_key.save()
        return True
    except APIKey.DoesNotExist:
        return False

def get_user_notifications(user_id, unread_only=False, limit=10):
    try:
        queryset = Notification.objects.filter(user_id=user_id)
        if unread_only:
            queryset = queryset.filter(is_read=False)
        queryset = queryset.order_by('-created_at')
        if limit:
            queryset = queryset[:limit]
        return [{
            "id": str(n.id),
            "title": n.title,
            "message": n.message,
            "type": n.type,
            "is_read": n.is_read,
            "created_at": n.created_at,
        } for n in queryset]
    except Exception as e:
        logger.error(f"Failed to get notifications: {e}")
        return []

def get_unread_notification_count(user_id):
    try:
        return Notification.objects.filter(user_id=user_id, is_read=False).count()
    except:
        return 0

def mark_notification_read(user_id, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id, user_id=user_id)
        notification.is_read = True
        notification.save()
        return True
    except Notification.DoesNotExist:
        return False

def create_notification(user_id, title, message, type='info'):
    from django.contrib.auth.models import User
    try:
        user = User.objects.get(id=user_id)
        Notification.objects.create(
            user=user,
            title=title,
            message=message,
            type=type,
            is_read=False
        )
        return True
    except Exception as e:
        logger.error(f"Failed to create notification: {e}")
        return False
