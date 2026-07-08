import re
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse
from django.conf import settings


class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        if path.startswith(settings.STATIC_URL) or path.startswith(settings.MEDIA_URL):
            return self.get_response(request)

        limits = getattr(settings, 'RATE_LIMITS', [
            (r'^/login/', 10, 60),
            (r'^/signup/', 5, 60),
            (r'^/password-reset/', 5, 60),
            (r'^/ai-convert/', 5, 60),
            (r'^/editor/[^/]+/reprocess/', 5, 60),
            (r'^/upload/', 10, 60),
            (r'^/editor/[^/]+/save/', 20, 60),
            (r'^/editor/[^/]+/compile/', 10, 60),
            (r'^/payment/create-checkout-session/', 10, 60),
            (r'^/payment/webhook/', 30, 60),
            (r'.*', 60, 60),
        ])

        ip = self._get_ip(request)

        for pattern, rate, window in limits:
            if re.search(pattern, path):
                cache_key = f"rl:{ip}:{pattern}"
                count = cache.get(cache_key, 0)
                if count >= rate:
                    return self._rate_limit_response(request)
                cache.set(cache_key, count + 1, window)
                break

        return self.get_response(request)

    def _get_ip(self, request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '127.0.0.1')

    def _rate_limit_response(self, request):
        is_json = self._wants_json(request)
        if is_json:
            return JsonResponse(
                {"status": "error", "message": "Too many requests. Please try again later."},
                status=429,
            )
        return HttpResponse(
            "Too many requests. Please try again later.",
            status=429,
            content_type='text/plain',
        )

    def _wants_json(self, request):
        accept = request.META.get('HTTP_ACCEPT', '')
        return ('application/json' in accept or
                request.GET.get('format') == 'json' or
                request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest')


class RowLevelSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.db import connection
        if connection.vendor != 'postgresql':
            return self.get_response(request)
        user_id = request.user.id if request.user.is_authenticated else None
        with connection.cursor() as cursor:
            if user_id:
                cursor.execute("SET LOCAL app.current_user_id = %s", [user_id])
            else:
                cursor.execute("SET LOCAL app.current_user_id = ''")
        return self.get_response(request)
