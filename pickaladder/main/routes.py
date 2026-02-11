from flask import current_app, send_from_directory
from . import bp

@bp.route('/service-worker.js')
def service_worker():
    return send_from_directory(current_app.static_folder, 'service-worker.js')
