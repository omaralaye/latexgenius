from django.contrib import admin
from .models import Template, Project

@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'category')
    search_fields = ('name', 'category')

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'status', 'last_modified')
    list_filter = ('status', 'owner')
    search_fields = ('title', 'owner__username')
