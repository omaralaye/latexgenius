from datetime import datetime
from django.utils import timezone
from django.conf import settings
from django.db.models import Q
from .models import Project, Template, AppSetting, Feature, Statistic, Testimonial, Notification, ConversionJob
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
        count, _ = Project.objects.filter(id=project_id).delete()
        if count > 0:
            logger.info(f"Project {project_id} deleted.")
            return True
        logger.warning(f"Project {project_id} not found for deletion.")
        return False
    except ValueError as e:
        logger.error(f"Failed to delete project {project_id} due to value error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred while deleting project {project_id}: {str(e)}")
        return False

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
def update_job_progress(job_id, status, message, percent):
    try:
        ConversionJob.objects.filter(id=job_id).update(
            status=status,
            progress_message=message,
            progress_percent=percent
        )
    except Exception as e:
        logger.error(f"Failed to update conversion job {job_id}: {e}")

def convert_to_latex_ai(content=None, file_path=None, template_content=None, conversion_job_id=None):
    """
    Converts document content or a file to LaTeX using Kimi K2.6 via NVIDIA API,
    optionally reporting progress to a ConversionJob.
    """
    input_text = ""
    if file_path:
        if conversion_job_id:
            update_job_progress(conversion_job_id, 'processing', 'Extracting text from document...', 10)
        try:
            input_text = pypandoc.convert_file(file_path, 'markdown')
        except Exception as e:
            logger.error(f"Pandoc conversion failed: {e}")
            try:
                with open(file_path, 'r', errors='ignore') as f:
                    input_text = f.read()
            except Exception as read_err:
                logger.error(f"Failed to read file: {read_err}")
                if conversion_job_id:
                    update_job_progress(conversion_job_id, 'failed', f'Failed to read file: {read_err}', 0)
                return None
    else:
        input_text = content

    if not input_text:
        logger.warning("AI conversion attempted with empty input.")
        if conversion_job_id:
            update_job_progress(conversion_job_id, 'failed', 'No content provided for conversion.', 0)
        return None

    if not settings.KIMI_API_KEY:
        logger.error("KIMI_API_KEY is not configured.")
        if conversion_job_id:
            update_job_progress(conversion_job_id, 'failed', 'KIMI_API_KEY is not configured.', 0)
        return None

    if conversion_job_id:
        update_job_progress(conversion_job_id, 'processing', 'Sending to Kimi K2.6 for LaTeX conversion...', 30)

    try:
        client = openai.OpenAI(api_key=settings.KIMI_API_KEY, base_url=settings.KIMI_BASE_URL)

        prompt = "Convert the following document into a high-quality, valid LaTeX document. Return ONLY the LaTeX code, starting from \\documentclass and ending with \\end{document}."
        if template_content:
            prompt += "\n\nUse the provided LaTeX template as the formatting and structure guide. Preserve the template style and incorporate the document content into that template."
            prompt += f"\n\nTemplate Content:\n{template_content}"
        prompt += f"\n\nDocument Content:\n{input_text}"

        if conversion_job_id:
            update_job_progress(conversion_job_id, 'processing', 'Kimi K2.6 is analyzing and generating LaTeX code...', 50)

        response = client.chat.completions.create(
            model=settings.KIMI_MODEL,
            messages=[
                {"role": "system", "content": "You are a LaTeX expert. Your task is to convert any provided document into a clean, well-structured LaTeX source code in accordance with the requested template."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
            top_p=1.00,
            extra_body={"chat_template_kwargs": {"thinking": False}},
            max_tokens=16384
        )

        if conversion_job_id:
            update_job_progress(conversion_job_id, 'processing', 'Post-processing generated LaTeX code...', 80)

        latex_code = response.choices[0].message.content

        if "```latex" in latex_code:
            latex_code = latex_code.split("```latex")[1].split("```")[0]
        elif "```" in latex_code:
            latex_code = latex_code.split("```")[1].split("```")[0]

        return latex_code.strip()
    except Exception as e:
        logger.error(f"Kimi API error: {e}")
        if conversion_job_id:
            update_job_progress(conversion_job_id, 'failed', f'Kimi AI error: {str(e)}', 0)
        return None

def run_conversion_job(job_id, project_id, file_path=None, content=None, template_content=None, delete_file=False):
    try:
        project = Project.objects.get(id=project_id)
        update_job_progress(job_id, 'processing', 'Starting conversion with Kimi K2.6...', 5)

        latex_code = convert_to_latex_ai(
            content=content,
            file_path=file_path,
            template_content=template_content,
            conversion_job_id=job_id
        )

        if delete_file and file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

        if latex_code:
            project.content = latex_code
            project.save()
            update_job_progress(job_id, 'completed', 'LaTeX conversion complete!', 100)
        else:
            update_job_progress(job_id, 'failed', 'AI conversion returned no output.', 0)
    except Project.DoesNotExist:
        update_job_progress(job_id, 'failed', 'Project not found.', 0)
    except Exception as e:
        logger.error(f"Conversion job {job_id} failed: {e}")
        update_job_progress(job_id, 'failed', f'Unexpected error: {str(e)}', 0)
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

def mark_all_notifications_read(user_id):
    try:
        Notification.objects.filter(user_id=user_id, is_read=False).update(is_read=True)
        return True
    except Exception as e:
        logger.error(f"Failed to mark all notifications as read: {e}")
        return False

def get_subscription_plans():
    from .models import SubscriptionPlan
    try:
        plans = SubscriptionPlan.objects.filter(is_active=True).order_by('sort_order')
        return [{
            "id": str(p.id),
            "name": p.name,
            "stripe_price_id_monthly": p.stripe_price_id_monthly,
            "stripe_price_id_yearly": p.stripe_price_id_yearly,
            "description": p.description,
            "features": p.get_features(),
            "monthly_price_cents": p.monthly_price_cents,
            "yearly_price_cents": p.yearly_price_cents,
            "monthly_price_dollars": p.monthly_price_dollars(),
            "yearly_price_dollars": p.yearly_price_dollars(),
            "sort_order": p.sort_order,
        } for p in plans]
    except Exception as e:
        logger.error(f"Failed to get subscription plans: {e}")
        return []

def get_user_subscription(user_id):
    from .models import UserSubscription
    try:
        sub = UserSubscription.objects.filter(user_id=user_id).first()
        if sub and sub.plan:
            return {
                "id": str(sub.id),
                "plan_id": str(sub.plan.id),
                "plan_name": sub.plan.name,
                "status": sub.status,
                "is_active": sub.is_active(),
                "stripe_customer_id": sub.stripe_customer_id,
                "stripe_subscription_id": sub.stripe_subscription_id,
                "current_period_start": sub.current_period_start,
                "current_period_end": sub.current_period_end,
                "cancel_at_period_end": sub.cancel_at_period_end,
                "trial_end": sub.trial_end,
            }
        return None
    except Exception as e:
        logger.error(f"Failed to get user subscription: {e}")
        return None

def user_is_pro(user_id):
    sub = get_user_subscription(user_id)
    if sub and sub.get("is_active"):
        return True
    return False

def create_stripe_checkout_session(user_id, price_id, success_url, cancel_url):
    import stripe
    from django.conf import settings
    from django.contrib.auth.models import User

    try:
        user = User.objects.get(id=user_id)
        stripe.api_key = settings.STRIPE_SECRET_KEY

        sub = UserSubscription.objects.filter(user_id=user_id).first()
        customer_id = sub.stripe_customer_id if sub and sub.stripe_customer_id else None

        session = stripe.checkout.Session.create(
            customer=customer_id,
            customer_email=customer_id and None or user.email,
            mode='subscription',
            line_items=[{"price": price_id, "quantity": 1}],
            metadata={"user_id": str(user_id)},
            success_url=success_url,
            cancel_url=cancel_url,
            subscription_data={
                "metadata": {"user_id": str(user_id)},
            },
        )

        return {"url": session.url, "session_id": session.id}
    except Exception as e:
        logger.error(f"Failed to create Stripe checkout session: {e}")
        return None

def create_stripe_customer_portal_session(user_id, return_url):
    import stripe
    from django.conf import settings
    from django.contrib.auth.models import User

    try:
        user = User.objects.get(id=user_id)
        stripe.api_key = settings.STRIPE_SECRET_KEY

        sub = UserSubscription.objects.filter(user_id=user_id).first()
        if not sub or not sub.stripe_customer_id:
            return None

        session = stripe.billing_portal.Session.create(
            customer=sub.stripe_customer_id,
            return_url=return_url,
        )

        return {"url": session.url}
    except Exception as e:
        logger.error(f"Failed to create customer portal session: {e}")
        return None

def cancel_subscription_at_period_end(user_id):
    import stripe
    from django.conf import settings

    try:
        sub = UserSubscription.objects.filter(user_id=user_id).first()
        if not sub or not sub.stripe_subscription_id:
            return False

        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe_sub = stripe.subscriptions.modify(
            sub.stripe_subscription_id,
            cancel_at_period_end=True,
        )

        sub.cancel_at_period_end = True
        sub.save()
        return True
    except Exception as e:
        logger.error(f"Failed to cancel subscription: {e}")
        return False

def reactivate_subscription(user_id):
    import stripe
    from django.conf import settings

    try:
        sub = UserSubscription.objects.filter(user_id=user_id).first()
        if not sub or not sub.stripe_subscription_id:
            return False

        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe_sub = stripe.subscriptions.modify(
            sub.stripe_subscription_id,
            cancel_at_period_end=False,
        )

        sub.cancel_at_period_end = False
        sub.save()
        return True
    except Exception as e:
        logger.error(f"Failed to reactivate subscription: {e}")
        return False

def update_subscription_from_stripe(stripe_subscription, user_subscription=None):
    from .models import SubscriptionPlan, UserSubscription
    from django.utils import timezone
    from datetime import datetime

    customer_id = stripe_subscription.get('customer')
    subscription_id = stripe_subscription.get('id')
    status = stripe_subscription.get('status')
    cancel_at_period_end = stripe_subscription.get('cancel_at_period_end', False)
    current_period_start = stripe_subscription.get('current_period_start')
    current_period_end = stripe_subscription.get('current_period_end')
    trial_end = stripe_subscription.get('trial_end')
    items = stripe_subscription.get('items', {}).get('data', [])
    metadata = stripe_subscription.get('metadata', {})
    user_id = metadata.get('user_id')

    if not user_id:
        return None

    price_id = items[0]['price']['id'] if items else None

    plan = None
    if price_id:
        plan = SubscriptionPlan.objects.filter(
            Q(stripe_price_id_monthly=price_id) | Q(stripe_price_id_yearly=price_id)
        ).first()

    def ts_to_datetime(ts):
        if ts:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        return None

    defaults = {
        'plan': plan,
        'status': status,
        'cancel_at_period_end': cancel_at_period_end,
        'current_period_start': ts_to_datetime(current_period_start),
        'current_period_end': ts_to_datetime(current_period_end),
        'trial_end': ts_to_datetime(trial_end),
        'stripe_customer_id': customer_id,
    }

    if user_subscription:
        for key, value in defaults.items():
            setattr(user_subscription, key, value)
        user_subscription.save()
        return user_subscription

    sub, created = UserSubscription.objects.update_or_create(
        stripe_subscription_id=subscription_id,
        defaults={
            'user_id': user_id,
            **defaults,
        }
    )
    return sub

def ensure_default_subscription(user):
    from .models import SubscriptionPlan, UserSubscription
    if not UserSubscription.objects.filter(user=user).exists():
        free_plan = SubscriptionPlan.objects.filter(name__iexact='free').first()
        UserSubscription.objects.create(
            user=user,
            plan=free_plan,
            status='active',
        )

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
