from django.contrib import admin
from .models import Template, Project, AppSetting, Feature, Statistic, Testimonial

@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'value')
    search_fields = ('key',)

@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ('title', 'order')
    list_editable = ('order',)

@admin.register(Statistic)
class StatisticAdmin(admin.ModelAdmin):
    list_display = ('label', 'value')

@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ('name', 'role')

@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'category')
    search_fields = ('name', 'category')

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'status', 'last_modified')
    list_filter = ('status', 'owner')
    search_fields = ('title', 'owner__username')
