from functools import wraps
from flask import g

def mock_login_required(f=None, admin_required=False):
    def decorator(func):
        @wraps(func)
        def decorated_function(*args, **kwargs):
            g.user = {"uid": "test_user_id", "isAdmin": admin_required}
            return func(*args, **kwargs)
        return decorated_function

    if f:
        return decorator(f)
    return decorator