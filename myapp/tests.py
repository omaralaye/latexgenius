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
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
import time

class RateLimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ratelimit@example.com', email='ratelimit@example.com', password='password123')

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
    def test_login_rate_limit(self):
        url = reverse('login')
        # Rate is 10/m for login
        for i in range(10):
            response = self.client.post(url, {'username': 'ratelimit@example.com', 'password': 'wrongpassword'})
            self.assertEqual(response.status_code, 200) # Form errors, but not rate limited yet

        # 11th attempt should be rate limited
        response = self.client.post(url, {'username': 'ratelimit@example.com', 'password': 'wrongpassword'})
        self.assertEqual(response.status_code, 200) # It returns 200 but with an error message in context
        self.assertContains(response, "Too many login attempts. Please try again later.")

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
    def test_signup_rate_limit(self):
        url = reverse('signup')
        # Rate is 5/m for signup
        for i in range(5):
            response = self.client.post(url, {'email': f'test{i}@example.com', 'password': 'password123', 'name': 'Test'})
            self.assertEqual(response.status_code, 302) # Redirect to dashboard
            self.client.logout()

        # 6th attempt should be rate limited
        response = self.client.post(url, {'email': 'final@example.com', 'password': 'password123', 'name': 'Test'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Too many signup attempts. Please try again later.")

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
    def test_save_project_rate_limit(self):
        self.client.login(username='ratelimit@example.com', password='password123')
        # Create a project first
        from myapp import services
        project_id = services.create_project(owner_id=self.user.id, title="Test", content="Content")

        url = reverse('save_project', kwargs={'project_id': project_id})
        # Rate is 20/m for save_project
        for i in range(20):
            response = self.client.post(url, {'content': f'content {i}'})
            self.assertEqual(response.status_code, 200)

        # 21st attempt should be rate limited
        response = self.client.post(url, {'content': 'final content'})
        self.assertEqual(response.status_code, 429)
        self.assertJSONEqual(response.content, {"status": "error", "message": "Too many requests. Please slow down."})

from django.core.files.uploadedfile import SimpleUploadedFile

class DocumentUploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser@example.com', password='password123')
        self.client.login(username='testuser@example.com', password='password123')

    def test_upload_valid_tex_file(self):
        content = b"\\documentclass{article}\\begin{document}Hello\\end{document}"
        uploaded_file = SimpleUploadedFile("test.tex", content, content_type="text/plain")

        response = self.client.post(reverse('upload_document'), {'document': uploaded_file})

        # Should redirect to editor
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/editor/'))

        # Check if project was created
        project = Project.objects.filter(owner=self.user, title="test").first()
        self.assertIsNotNone(project)
        self.assertEqual(project.content, content.decode('utf-8'))
        self.assertEqual(project.filename, "test.tex")

    def test_upload_invalid_file_extension(self):
        content = b"some content"
        uploaded_file = SimpleUploadedFile("test.txt", content, content_type="text/plain")

        response = self.client.post(reverse('upload_document'), {'document': uploaded_file})

        # Should redirect back to dashboard
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))

from unittest.mock import patch, MagicMock

class CompilationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser@example.com', password='password123')
        self.client.login(username='testuser@example.com', password='password123')
        self.project_id = services.create_project(
            owner_id=self.user.id,
            title="Test Project",
            content="\\documentclass{article}\\begin{document}Hello\\end{document}",
            filename="main.tex"
        )

    @patch('httpx.post')
    def test_compile_project_success(self, mock_post):
        # Mock successful response from latex-online
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"%PDF-1.4 binary data"
        mock_post.return_value = mock_response

        url = reverse('compile_project', kwargs={'project_id': self.project_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response.content, b"%PDF-1.4 binary data")

        # Verify httpx.post was called correctly
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn('/data', args[0])
        self.assertEqual(kwargs['params'], {'target': 'main.tex'})
        self.assertIn('file', kwargs['files'])

    @patch('httpx.post')
    def test_compile_project_failure(self, mock_post):
        # Mock failed response from latex-online
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "LaTeX Error: Missing \begin{document}"
        mock_post.return_value = mock_response

        url = reverse('compile_project', kwargs={'project_id': self.project_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Compilation failed", response.content)
        self.assertIn(b"LaTeX Error", response.content)

    def test_upload_no_file(self):
        response = self.client.post(reverse('upload_document'))

        # Should redirect back to dashboard
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))
