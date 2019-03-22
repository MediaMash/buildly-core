import uuid
from typing import Union

from django.db import models
from django.contrib.postgres import fields
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.contrib.postgres.fields import JSONField
from django.core.exceptions import ValidationError
from django.contrib.sites.models import Site
try:
    from django.utils import timezone
except ImportError:
    from datetime import datetime as timezone
from simple_history.models import HistoricalRecords

ROLE_ORGANIZATION_ADMIN = 'OrgAdmin'
ROLE_WORKFLOW_ADMIN = 'WorkflowAdmin'
ROLE_WORKFLOW_TEAM = 'WorkflowTeam'
ROLE_VIEW_ONLY = 'ViewOnly'
ROLES = (
    (ROLE_ORGANIZATION_ADMIN, ROLE_ORGANIZATION_ADMIN),
    (ROLE_WORKFLOW_ADMIN, ROLE_WORKFLOW_ADMIN),
    (ROLE_WORKFLOW_TEAM, ROLE_WORKFLOW_TEAM),
    (ROLE_VIEW_ONLY, ROLE_VIEW_ONLY),
)
DEFAULT_PROGRAM_NAME = 'Default program'


class CoreSites(models.Model):
    name = models.CharField(blank=True, null=True, max_length=255)
    site = models.ForeignKey(Site, on_delete=models.CASCADE)
    privacy_disclaimer = models.TextField(blank=True, null=True)
    created = models.DateTimeField(auto_now=False, blank=True, null=True)
    updated = models.DateTimeField(auto_now=False, blank=True, null=True)
    whitelisted_domains = models.TextField("Whitelisted Domains", null=True, blank=True)

    class Meta:
        verbose_name = "Core Site"
        verbose_name_plural = "Core Sites"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if kwargs.pop('new_entry', True):
            self.created = timezone.now()
        else:
            self.updated = timezone.now()
        return super(CoreSites, self).save(*args, **kwargs)


class Industry(models.Model):
    name = models.CharField("Industry Name", max_length=255, blank=True, default="Humanitec")
    description = models.TextField("Description/Notes", max_length=765, null=True, blank=True)
    create_date = models.DateTimeField(null=True, blank=True)
    edit_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('name',)
        verbose_name_plural = "Industries"
        app_label = 'workflow'

    def save(self, *args, **kwargs):
        if self.create_date is None:
            self.create_date = timezone.now()
        self.edit_date = timezone.now()
        super(Industry, self).save()

    def __str__(self):
        return self.name


class Organization(models.Model):
    organization_uuid = models.CharField(max_length=255, verbose_name='Organization UUID', default=uuid.uuid4, unique=True)
    name = models.CharField("Organization Name", max_length=255, blank=True, default="Humanitec", help_text="Each end user must be grouped into an organization")
    description = models.TextField("Description/Notes", max_length=765, null=True, blank=True, help_text="Descirption of organization")
    organization_url = models.CharField(blank=True, null=True, max_length=255, help_text="Link to organizations external web site")
    industry = models.ManyToManyField(Industry, blank=True, help_text="Type of Industry the organization belongs to if any")
    level_1_label = models.CharField("Workflow Level 1 label", default="Program", max_length=255, blank=True, help_text="Label to display if needed for workflow i.e. Top Level Navigation, Primary, Program, etc. ")
    level_2_label = models.CharField("Workflow Level 2 label", default="Project", max_length=255, blank=True, help_text="Label to display if needed for workflow i.e. Second Level Navigation, Major,  Project, etc. ")
    level_3_label = models.CharField("Workflow Level 3 label", default="Component", max_length=255, blank=True, help_text="Label to display if needed for workflow i.e. Third Level Navigation, Minor,  Activity, etc. ")
    level_4_label = models.CharField("Workflow Level 4 label", default="Activity", max_length=255, blank=True, help_text="Label to display if needed for workflow i.e. Fourth Level Navigation, Sub,  Sub-Activity, etc. ")
    create_date = models.DateTimeField(null=True, blank=True)
    edit_date = models.DateTimeField(null=True, blank=True)
    subscription_id = models.CharField(blank=True, null=True, max_length=50)
    used_seats = models.IntegerField(blank=True, null=True, default=0)
    oauth_domains = fields.ArrayField(models.CharField("OAuth Domains", max_length=255, null=True, blank=True), null=True, blank=True)
    date_format = models.CharField("Date Format", max_length=50, blank=True, default="DD.MM.YYYY")
    phone = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        ordering = ('name',)
        verbose_name_plural = "Organizations"
        app_label = 'workflow'

    def save(self, *args, **kwargs):
        if self.create_date is None:
            self.create_date = timezone.now()
        self.edit_date = timezone.now()
        super(Organization, self).save()

    def __str__(self):
        return self.name


TITLE_CHOICES = (
    ('mr', 'Mr.'),
    ('mrs', 'Mrs.'),
    ('ms', 'Ms.'),
)


class CoreUser(AbstractUser):
    """
    CoreUser is the registered user who belongs to some organization and can manage its projects.
    """
    core_user_uuid = models.CharField(max_length=255, verbose_name='CoreUser UUID', default=uuid.uuid4, unique=True)
    title = models.CharField(blank=True, null=True, max_length=3, choices=TITLE_CHOICES)
    contact_info = models.CharField(blank=True, null=True, max_length=255)
    organization = models.ForeignKey(Organization, blank=True, null=True, on_delete=models.CASCADE)
    core_groups = models.ManyToManyField('CoreGroup', verbose_name='User groups', blank=True, related_name='user_set', related_query_name='user')
    privacy_disclaimer_accepted = models.BooleanField(default=False)
    create_date = models.DateTimeField(default=timezone.now)
    edit_date = models.DateTimeField(null=True, blank=True)
    # We need to override this field to specify different `related_name` to avoid conflict with User model
    # (probably we can remove it when `django.contrib.auth` will be excluded from INSTALLED_APPS)
    user_permissions = models.ManyToManyField(Permission, verbose_name='User permissions', blank=True,
                                              help_text='Specific permissions for this user.',
                                              related_name="core_user_set", related_query_name="core_user")

    class Meta:
        ordering = ('first_name',)

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        if self.create_date is None:
            self.create_date = timezone.now()
        self.edit_date = timezone.now()

        super(CoreUser, self).save()

    def is_org_admin(self) -> bool:
        """
        Checks if user has Organization admin role
        """
        if not hasattr(self, '_is_org_admin'):
            self._is_org_admin = ROLE_ORGANIZATION_ADMIN in self.groups.values_list('name', flat=True)
        return self._is_org_admin


class Internationalization(models.Model):
    language = models.CharField("Language", blank=True, null=True, max_length=100)
    language_file = JSONField()
    create_date = models.DateTimeField(null=True, blank=True)
    edit_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('language',)

    def __str__(self):
        return self.language

    def save(self, *args, **kwargs):
        if self.create_date is None:
            self.create_date = timezone.now()
        self.edit_date = timezone.now()
        super(Internationalization, self).save()


class WorkflowLevel1(models.Model):
    level1_uuid = models.CharField(max_length=255, editable=False, verbose_name='WorkflowLevel1 UUID', default=uuid.uuid4, unique=True)
    unique_id = models.CharField("ID", max_length=255, blank=True, null=True, help_text="User facing unique ID field if needed")
    name = models.CharField("Name", max_length=255, blank=True, help_text="Top level workflow can have child workflowleves, name it according to it's grouping of children")
    organization = models.ForeignKey(Organization, blank=True, on_delete=models.CASCADE, null=True, help_text='Related Org to associate with')
    description = models.TextField("Description", max_length=765, null=True, blank=True, help_text='Describe how this collection of related workflows are used')
    user_access = models.ManyToManyField(CoreUser, blank=True)
    start_date = models.DateTimeField(null=True, blank=True, help_text='If required a time span can be associated with workflow level')
    end_date = models.DateTimeField(null=True, blank=True, help_text='If required a time span can be associated with workflow level')
    create_date = models.DateTimeField(null=True, blank=True)
    edit_date = models.DateTimeField(null=True, blank=True)
    sort = models.IntegerField(default=0)  #sort array

    class Meta:
        ordering = ('name',)
        verbose_name = "Workflow Level 1"
        verbose_name_plural = "Workflow Level 1"

    def save(self, *args, **kwargs):
        if not 'force_insert' in kwargs:
            kwargs['force_insert'] = False
        if self.create_date is None:
            self.create_date = timezone.now()
        self.edit_date = timezone.now()

        super(WorkflowLevel1, self).save()

    def delete(self, *args, **kwargs):
        super(WorkflowLevel1, self).delete(*args, **kwargs)

    def __str__(self):
        if self.organization:
            return f'{self.name} <{self.organization.name}>'
        else:
            return self.name


class WorkflowLevel2(models.Model):
    description = models.TextField("Description", blank=True, null=True, help_text="Description of the workflow level use")
    level2_uuid = models.CharField(max_length=255, editable=False, verbose_name='WorkflowLevel2 UUID', default=uuid.uuid4, unique=True, blank=True, help_text="Unique ID")
    name = models.CharField("Name", max_length=255, help_text="Name of workflow level as it relates to workflow level 1")
    notes = models.TextField(blank=True, null=True)
    parent_workflowlevel2 = models.IntegerField("Parent", default=0, blank=True, help_text="Workflow level 2 can relate to another workflow level 2 creating multiple levels of relationships")
    short_name = models.CharField("Code", max_length=20, blank=True, null=True, help_text="Shortened name autogenerated")
    workflowlevel1 = models.ForeignKey(WorkflowLevel1, verbose_name="Workflow Level 1", on_delete=models.CASCADE, related_name="workflowlevel2", help_text="Primary or parent Workflow")
    create_date = models.DateTimeField("Date Created", null=True, blank=True)
    created_by = models.ForeignKey(CoreUser, related_name='workflowlevel2', null=True, blank=True, on_delete=models.SET_NULL)
    edit_date = models.DateTimeField("Last Edit Date", null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ('name',)
        verbose_name = "Workflow Level 2"
        verbose_name_plural = "Workflow Level 2"

    def save(self, *args, **kwargs):
        if self.create_date is None:
            self.create_date = timezone.now()
        self.edit_date = timezone.now()

        super(WorkflowLevel2, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        super(WorkflowLevel2, self).delete(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def organization(self) -> Union[Organization, None]:
        return self.workflowlevel1.organization


class CoreGroup(models.Model):
    """
    CoreGroup model defines the groups of the users with specific permissions in the context of given workflow
    (it could be Workflow Level 1 or Workflow Level 2).
    If there's no workflow attached than it's a global Role (such as Organization Admin)
    Permissions field is the decimal integer from 0 to 15 converted from 4-bit binary, each bit indicates permissions
    for CRUD. For example: 12 -> 1100 -> CR__ (allowed to Create and Read).
    """
    uuid = models.CharField('CoreGroup UUID', max_length=255, default=uuid.uuid4, unique=True)
    name = models.CharField('Name of the role', max_length=80)
    workflowlevel1 = models.ForeignKey(WorkflowLevel1, null=True, blank=True, on_delete=models.SET_NULL)
    workflowlevel2 = models.ForeignKey(WorkflowLevel2, null=True, blank=True, on_delete=models.SET_NULL)
    permissions = models.PositiveSmallIntegerField('Permissions', help_text='Decimal integer from 0 to 15 converted from 4-bit binary, each bit indicates permissions for CRUD')
    create_date = models.DateTimeField(default=timezone.now)
    edit_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('role',)

    def __str__(self):
        wf = self.workflowlevel2 or self.workflowlevel1
        return f'{self.role} <{wf}>'

    def save(self, *args, **kwargs):
        self.edit_date = timezone.now()
        super(CoreGroup, self).save(*args, **kwargs)

    @property
    def organization(self) -> Union[Organization, None]:
        if self.workflowlevel2:
            return self.workflowlevel2.organization
        if self.workflowlevel1:
            return self.workflowlevel1.organization
        return None

    @property
    def display_permissions(self) -> str:
        return '{0:b}'.format(self.permissions if self.permissions < 16 else 15)


class WorkflowTeam(models.Model):
    """
    WorkflowTeam defines m2m relations between CoreUser and Workflowlevel1.
    It also defines a role for this relationship (as a fk to Group instance).
    """
    team_uuid = models.CharField(max_length=255, editable=False, verbose_name='WorkflowLevel1 UUID', default=uuid.uuid4, unique=True)
    workflow_user = models.ForeignKey(CoreUser, blank=True, null=True, on_delete=models.CASCADE, related_name="auth_approving", help_text='User with access/permissions to related workflowlevels')
    workflowlevel1 = models.ForeignKey(WorkflowLevel1, null=True, on_delete=models.CASCADE, blank=True, help_text='Related workflowlevel 1')
    start_date = models.DateTimeField(null=True, blank=True, help_text='If required a time span can be associated with workflow level access')
    end_date = models.DateTimeField(null=True, blank=True, help_text='If required a time span can be associated with workflow level access expiration')
    status = models.CharField(max_length=255, null=True, blank=True, help_text='Active status of access')
    role = models.ForeignKey(Group, null=True, blank=True, on_delete=models.CASCADE, help_text='Type of access via related group')
    create_date = models.DateTimeField(null=True, blank=True)
    edit_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('workflow_user',)
        verbose_name = "Workflow Team"
        verbose_name_plural = "Workflow Teams"

    def clean(self):
        if self.role and self.role.name == ROLE_ORGANIZATION_ADMIN:
            raise ValidationError(
                'Workflowteam role can not be ROLE_ORGANIZATION_ADMIN'
            )

    def save(self, *args, **kwargs):
        if self.create_date is None:
            self.create_date = timezone.now()
        self.edit_date = timezone.now()
        super(WorkflowTeam, self).save()

    def __str__(self):
        return f'{self.workflow_user} - {self.role} <{self.workflowlevel1}>'


class WorkflowLevel2Sort(models.Model):
    workflowlevel1 = models.ForeignKey(WorkflowLevel1, null=True, on_delete=models.CASCADE, blank=True)
    workflowlevel2_parent_id = models.ForeignKey(WorkflowLevel2, on_delete=models.CASCADE, null=True, blank=True)
    workflowlevel2_id = models.IntegerField("ID to be Sorted", default=0)
    sort_array = JSONField(null=True, blank=True, help_text="Sorted JSON array of workflow levels")
    create_date = models.DateTimeField(null=True, blank=True)
    edit_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('workflowlevel1', 'workflowlevel2_id')
        verbose_name = "Workflow Level Sort"
        verbose_name_plural = "Workflow Level Sort"

    def save(self, *args, **kwargs):
        if self.create_date is None:
            self.create_date = timezone.now()
        self.edit_date = timezone.now()
        super(WorkflowLevel2Sort, self).save()

    def __str__(self):
        return self.workflowlevel1


TEMPLATE_RESET_PASSWORD, TEMPLATE_INVITE = 1, 2
TEMPLATE_TYPES = (
    (TEMPLATE_RESET_PASSWORD, 'Password resetting'),
    (TEMPLATE_INVITE, 'Invitation'),
)


class EmailTemplate(models.Model):
    """Stores e-mail templates specific to organization
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, verbose_name='Organization')
    subject = models.CharField('Subject', max_length=255)
    type = models.PositiveSmallIntegerField('Type of template', choices=TEMPLATE_TYPES)
    template = models.TextField("Reset password e-mail template (text)", null=True, blank=True)
    template_html = models.TextField("Reset password e-mail template (HTML)", null=True, blank=True)

    class Meta:
        unique_together = ('organization', "type")
        verbose_name = "Email Template"
        verbose_name_plural = "Email Templates"

    def __str__(self):
        return f'{self.type} ({self.organization})'
