from django.db import models
from django.contrib.auth.models import User

class Template(models.Model):
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50)
    image_url = models.URLField()
    content = models.TextField(help_text="Default LaTeX content for this template")

    def __str__(self):
        return self.name

class Project(models.Model):
    STATUS_CHOICES = [
        ('compiled', 'Compiled'),
        ('draft', 'Draft'),
    ]

    title = models.CharField(max_length=200)
    filename = models.CharField(max_length=100, default='main.tex')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects')
    content = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    last_modified = models.DateTimeField(auto_now=True)
    collaborators = models.ManyToManyField(User, related_name='collaborated_projects', blank=True)

    def __str__(self):
        return self.title
