import json
import time
from django.utils.deprecation import MiddlewareMixin

class VisitorTrackerMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return None

        visitor_id = request.COOKIES.get('remarobe_vid')
        
        # Safely resolve user if AuthenticationMiddleware has executed
        user = 'Anonymous'
        if hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user.username
        
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
            "visitor_id": visitor_id or "new",
            "user": user,
            "path": request.path,
            "method": request.method,
            "ip": request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR')),
            "user_agent": request.META.get('HTTP_USER_AGENT', '')[:100]
        }

        try:
            with open('/var/www/Gadget/visitor_events.log', 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception:
            pass

    def process_response(self, request, response):
        if not request.COOKIES.get('remarobe_vid'):
            import uuid
            response.set_cookie('remarobe_vid', str(uuid.uuid4()), max_age=31536000, httponly=True, samesite='Lax')
        return response
