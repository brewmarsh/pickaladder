import os
from pickaladder import create_app
from firebase_admin import firestore
import unittest.mock
from tests.mock_utils import patch_mockfirestore

patch_mockfirestore()

app = create_app({'TESTING': True, 'SECRET_KEY': 'test', 'WTF_CSRF_ENABLED': False})

with app.app_context():
    with app.test_request_context():
        from flask import g, session
        from pickaladder.user.helpers import wrap_user

        # Mock user
        admin_user = {
            'uid': 'admin_uid',
            'username': 'admin',
            'name': 'Admin User',
            'email': 'admin@example.com',
            'isAdmin': True
        }
        g.user = wrap_user(admin_user, uid='admin_uid')
        session['user_id'] = 'admin_uid'
        session['is_admin'] = True

        # Mock Firestore client
        mock_db = unittest.mock.MagicMock()

        # Mock total users count
        mock_users_count = unittest.mock.MagicMock()
        mock_users_count.get.return_value = [unittest.mock.MagicMock(value=150)]
        mock_db.collection.return_value.count.return_value = mock_users_count

        # Mock active tournaments count
        mock_tournaments_count = unittest.mock.MagicMock()
        mock_tournaments_count.get.return_value = [unittest.mock.MagicMock(value=5)]

        # Mock recent matches count
        mock_matches_count = unittest.mock.MagicMock()
        mock_matches_count.get.return_value = [unittest.mock.MagicMock(value=12)]

        # Set up side effects for collection calls
        def collection_side_effect(name):
            mock_coll = unittest.mock.MagicMock()
            if name == 'users':
                mock_coll.count.return_value = mock_users_count
                mock_coll.limit.return_value.stream.return_value = []
                return mock_coll
            if name == 'tournaments':
                mock_coll.where.return_value.count.return_value = mock_tournaments_count
                return mock_coll
            if name == 'matches':
                mock_coll.where.return_value.count.return_value = mock_matches_count
                return mock_coll
            if name == 'settings':
                mock_doc = unittest.mock.MagicMock()
                mock_doc.get.return_value.exists = False
                mock_coll.document.return_value = mock_doc
                return mock_coll
            return unittest.mock.MagicMock()

        mock_db.collection.side_effect = collection_side_effect

        with unittest.mock.patch('firebase_admin.firestore.client', return_value=mock_db):
            from flask import render_template
            from pickaladder.admin.services import AdminService
            from pickaladder.user import UserService

            # Manually call the route logic
            admin_stats = AdminService.get_admin_stats(mock_db)
            users = []
            email_verification_setting = {"value": False}

            html = render_template(
                "admin/admin.html",
                admin_stats=admin_stats,
                users=users,
                email_verification_setting=email_verification_setting,
            )

            with open('admin_rendered.html', 'w') as f:
                f.write(html)

            # Also render footer to verify branding
            footer_html = render_template("footer.html", current_year=2024, app_version="0.9.47")
            with open('footer_rendered.html', 'w') as f:
                f.write(footer_html)
