from django.contrib.auth.models import AnonymousUser

class ClerkFixMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if hasattr(request, 'user') and request.user is None:
            request.user = AnonymousUser()
        return self.get_response(request)
