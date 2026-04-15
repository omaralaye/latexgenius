from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.urls import reverse
from myapp.models import Project
from myapp import services

class DashboardTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='testuser', password='password123')

    def test_dashboard_with_valid_projects(self):
        Project.objects.create(owner=self.user, title='Project 1')
        self.client.login(username='testuser', password='password123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Project 1')
        self.assertContains(response, '/editor/1/')

    def test_dashboard_with_partially_unsaved_project(self):
        # This shouldn't happen easily with Django ORM but we test our safeguard
        projects = [
            {'id': '1', 'title': 'Valid Project', 'status': 'draft', 'last_modified': '2026-04-15T12:00:00', 'filename': 'main.tex'},
            {'id': '', 'title': 'Invalid Project', 'status': 'draft', 'last_modified': '2026-04-15T12:00:00', 'filename': 'main.tex'}
        ]
        # We can't easily force services to return this without mocking,
        # but we can test the template rendering logic if we were to pass it.
        # For now, let's just ensure the service layer filters correctly.

        p_valid = Project.objects.create(owner=self.user, title='Valid')

        # Manually verify serialize_project with unsaved project
        p_unsaved = Project(owner=self.user, title='Unsaved')
        self.assertIsNone(services.serialize_project(p_unsaved))

        # Verify get_user_projects only returns the saved one
        user_projects = services.get_user_projects(self.user.id)
        self.assertEqual(len(user_projects), 1)
        self.assertEqual(user_projects[0]['title'], 'Valid')

    def test_serialize_project_none(self):
        self.assertIsNone(services.serialize_project(None))
