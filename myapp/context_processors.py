from django.conf import settings
from . import services

def subscription_context(request):
    if request.user.is_authenticated:
        services.ensure_default_subscription(request.user)
        user_sub = services.get_user_subscription(request.user.id)
        return {
            'user_subscription': user_sub,
            'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
        }
    return {
        'user_subscription': None,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
    }
