from django.conf import settings

def clerk_settings(request):
    return {
        'CLERK_PUBLISHABLE_KEY': getattr(settings, 'CLERK_PUBLISHABLE_KEY', ''),
    }
