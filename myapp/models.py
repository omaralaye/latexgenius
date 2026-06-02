from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
import json

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True, default='')
    avatar_url = models.URLField(max_length=500, blank=True, default='')
    affiliation = models.CharField(max_length=200, blank=True, default='')
    website = models.URLField(max_length=500, blank=True, default='')
    github = models.CharField(max_length=100, blank=True, default='')
    google_scholar = models.URLField(max_length=500, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

class Template(models.Model):
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50)
    image_url = models.URLField(max_length=500)
    content = models.TextField(help_text="Default LaTeX content for this template")

    def __str__(self):
        return self.name

class AppSetting(models.Model):
    key = models.CharField(max_length=50, unique=True)
    value = models.TextField()
    description = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.key

class Feature(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=50, help_text="Material symbol name")
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title

class Statistic(models.Model):
    label = models.CharField(max_length=100)
    value = models.CharField(max_length=50)
    description = models.TextField()
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.label

class Testimonial(models.Model):
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=100)
    quote = models.TextField()
    image_url = models.URLField(max_length=500, blank=True, null=True)

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

class Notification(models.Model):
    TYPE_CHOICES = [
        ('info', 'Information'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='info')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.user.username}"

class ProjectFile(models.Model):
    FILE_TYPE_CHOICES = [
        ('tex', 'LaTeX File'),
        ('bib', 'Bibliography'),
        ('image', 'Image'),
        ('folder', 'Folder'),
        ('other', 'Other'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='files')
    name = models.CharField(max_length=200)
    path = models.CharField(max_length=500, default='')
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default='tex')
    content = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=False)
    parent_folder = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['path', 'name']
        unique_together = ['project', 'path', 'name']

    def __str__(self):
        return f"{self.name} - {self.project.title}"

class ProjectVersion(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='versions')
    content = models.TextField()
    version_number = models.IntegerField(default=1)
    message = models.CharField(max_length=500, blank=True, default='')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_versions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version_number']
        unique_together = ['project', 'version_number']

    def __str__(self):
        return f"v{self.version_number} - {self.project.title}"

class UserPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences')
    dark_mode = models.BooleanField(default=False)
    auto_compile = models.BooleanField(default=True)
    font_size = models.CharField(max_length=10, default='14px')
    editor_theme = models.CharField(max_length=50, default='default')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s preferences"

@receiver(post_save, sender=User)
def create_user_preferences(sender, instance, created, **kwargs):
    if created:
        UserPreference.objects.create(user=instance)

@receiver(post_save, sender=User)
def create_user_subscription(sender, instance, created, **kwargs):
    if created:
        free_plan = SubscriptionPlan.objects.filter(name__iexact='free').first()
        UserSubscription.objects.create(
            user=instance,
            plan=free_plan,
            status='active',
        )

class ShareInvitation(models.Model):
    PERMISSION_CHOICES = [
        ('read', 'Read Only'),
        ('write', 'Can Edit'),
        ('admin', 'Admin'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='share_invitations')
    inviter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invitations')
    invitee_email = models.EmailField()
    invitee = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='received_invitations')
    permission = models.CharField(max_length=20, choices=PERMISSION_CHOICES, default='read')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    token = models.CharField(max_length=64, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.token:
            import secrets
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invitation for {self.invitee_email} to {self.project.title}"

class ConversionJob(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='conversion_jobs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress_message = models.TextField(default='Initializing conversion...')
    progress_percent = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ConversionJob {self.id} for {self.project.title} - {self.status}"

class ConversionStats(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='conversion_stats')
    confidence_score = models.FloatField(null=True, blank=True)
    math_symbol_count = models.IntegerField(default=0)
    section_count = models.IntegerField(default=0)
    citation_count = models.IntegerField(default=0)
    table_count = models.IntegerField(default=0)
    figure_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Stats for {self.project.title}"

class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100)
    stripe_price_id_monthly = models.CharField(max_length=100, blank=True, default='')
    stripe_price_id_yearly = models.CharField(max_length=100, blank=True, default='')
    description = models.TextField(blank=True, default='')
    features = models.TextField(blank=True, default='[]', help_text="JSON array of feature strings")
    monthly_price_cents = models.IntegerField(default=0)
    yearly_price_cents = models.IntegerField(default=0)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order']

    def get_features(self):
        try:
            return json.loads(self.features) if self.features else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_features(self, features_list):
        self.features = json.dumps(features_list)

    def monthly_price_dollars(self):
        return self.monthly_price_cents / 100

    def yearly_price_dollars(self):
        return self.yearly_price_cents / 100

    def __str__(self):
        return self.name

class UserSubscription(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('canceled', 'Canceled'),
        ('past_due', 'Past Due'),
        ('trialing', 'Trialing'),
        ('unpaid', 'Unpaid'),
        ('incomplete', 'Incomplete'),
        ('incomplete_expired', 'Incomplete Expired'),
        ('paused', 'Paused'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name='subscriptions')
    stripe_subscription_id = models.CharField(max_length=100, blank=True, default='')
    stripe_customer_id = models.CharField(max_length=100, blank=True, default='')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='active')
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    trial_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_active(self):
        return self.status in ('active', 'trialing')

    def __str__(self):
        return f"{self.user.username} - {self.plan.name if self.plan else 'No Plan'} ({self.status})"
