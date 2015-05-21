from django.db import models
from core.models import PlCoreBase,SingletonModel,PlCoreBaseManager
from core.models.plcorebase import StrippedCharField
from xos.exceptions import *
import json

class Service(PlCoreBase):
    # when subclassing a service, redefine KIND to describe the new service
    KIND = "generic"

    description = models.TextField(max_length=254,null=True, blank=True,help_text="Description of Service")
    enabled = models.BooleanField(default=True)
    kind = StrippedCharField(max_length=30, help_text="Kind of service", default=KIND)
    name = StrippedCharField(max_length=30, help_text="Service Name")
    versionNumber = StrippedCharField(max_length=30, help_text="Version of Service Definition")
    published = models.BooleanField(default=True)
    view_url = StrippedCharField(blank=True, null=True, max_length=1024)
    icon_url = StrippedCharField(blank=True, null=True, max_length=1024)
    public_key = models.TextField(null=True, blank=True, max_length=1024, help_text="Public key string")

    def __init__(self, *args, **kwargs):
        # for subclasses, set the default kind appropriately
        self._meta.get_field("kind").default = self.KIND
        super(Service, self).__init__(*args, **kwargs)

    @classmethod
    def get_service_objects(cls):
        return cls.objects.filter(kind = cls.KIND)

    def __unicode__(self): return u'%s' % (self.name)

    def can_update(self, user):
        return user.can_update_service(self, allow=['admin'])
     
    def get_scalable_nodes(self, slice, max_per_node=None, exclusive_slices=[]):
        """
             Get a list of nodes that can be used to scale up a slice.

                slice - slice to scale up
                max_per_node - maximum numbers of slivers that 'slice' can have on a single node
                exclusive_slices - list of slices that must have no nodes in common with 'slice'.
        """

        from core.models import Node, Sliver # late import to get around order-of-imports constraint in __init__.py

        nodes = list(Node.objects.all())

        conflicting_slivers = Sliver.objects.filter(slice__in = exclusive_slices)
        conflicting_nodes = Node.objects.filter(slivers__in = conflicting_slivers)

        nodes = [x for x in nodes if x not in conflicting_nodes]

        # If max_per_node is set, then limit the number of slivers this slice
        # can have on a single node.
        if max_per_node:
            acceptable_nodes = []
            for node in nodes:
                existing_count = node.slivers.filter(slice=slice).count()
                if existing_count < max_per_node:
                    acceptable_nodes.append(node)
            nodes = acceptable_nodes

        return nodes

    def pick_node(self, slice, max_per_node=None, exclusive_slices=[]):
        # Pick the best node to scale up a slice.

        nodes = self.get_scalable_nodes(slice, max_per_node, exclusive_slices)
        nodes = sorted(nodes, key=lambda node: node.slivers.all().count())
        if not nodes:
            return None
        return nodes[0]

    def adjust_scale(self, slice_hint, scale, max_per_node=None, exclusive_slices=[]):
        from core.models import Sliver # late import to get around order-of-imports constraint in __init__.py

        slices = [x for x in self.slices.all() if slice_hint in x.name]
        for slice in slices:
            while slice.slivers.all().count() > scale:
                s = slice.slivers.all()[0]
                # print "drop sliver", s
                s.delete()

            while slice.slivers.all().count() < scale:
                node = self.pick_node(slice, max_per_node, exclusive_slices)
                if not node:
                    # no more available nodes
                    break

                image = slice.default_image
                if not image:
                    raise XOSConfigurationError("No default_image for slice %s" % slice.name)

                flavor = slice.default_flavor
                if not flavor:
                    raise XOSConfigurationError("No default_flavor for slice %s" % slice.name)

                s = Sliver(slice=slice,
                           node=node,
                           creator=slice.creator,
                           image=image,
                           flavor=flavor,
                           deployment=node.site_deployment.deployment)
                s.save()

                # print "add sliver", s

class ServiceAttribute(PlCoreBase):
    name = models.SlugField(help_text="Attribute Name", max_length=128)
    value = StrippedCharField(help_text="Attribute Value", max_length=1024)
    service = models.ForeignKey(Service, related_name='serviceattributes', help_text="The Service this attribute is associated with")

class ServiceRole(PlCoreBase):
    ROLE_CHOICES = (('admin','Admin'),)
    role = StrippedCharField(choices=ROLE_CHOICES, unique=True, max_length=30)

    def __unicode__(self):  return u'%s' % (self.role)

class ServicePrivilege(PlCoreBase):
    user = models.ForeignKey('User', related_name='serviceprivileges')
    service = models.ForeignKey('Service', related_name='serviceprivileges')
    role = models.ForeignKey('ServiceRole',related_name='serviceprivileges')

    class Meta:
        unique_together =  ('user', 'service', 'role')

    def __unicode__(self):  return u'%s %s %s' % (self.service, self.user, self.role)

    def can_update(self, user):
        if not self.service.enabled:
            raise PermissionDenied, "Cannot modify permission(s) of a disabled service"
        return self.service.can_update(user)

    def save(self, *args, **kwds):
        if not self.service.enabled:
            raise PermissionDenied, "Cannot modify permission(s) of a disabled service"
        super(ServicePrivilege, self).save(*args, **kwds)

    def delete(self, *args, **kwds):
        if not self.service.enabled:
            raise PermissionDenied, "Cannot modify permission(s) of a disabled service"
        super(ServicePrivilege, self).delete(*args, **kwds)                    
    
    @staticmethod
    def select_by_user(user):
        if user.is_admin:
            qs = ServicePrivilege.objects.all()
        else:
            qs = SitePrivilege.objects.filter(user=user)
        return qs        

class Tenant(PlCoreBase):
    """ A tenant is a relationship between two entities, a subscriber and a
        provider.

        The subscriber can be a User, a Service, or a Tenant.

        The provider is always a Service.
    """

    CONNECTIVITY_CHOICES = (('public', 'Public'), ('private', 'Private'), ('na', 'Not Applicable'))

    # when subclassing a service, redefine KIND to describe the new service
    KIND = "generic"

    kind = StrippedCharField(max_length=30, default=KIND)
    provider_service = models.ForeignKey(Service, related_name='tenants')
    subscriber_service = models.ForeignKey(Service, related_name='subscriptions', blank=True, null=True)
    subscriber_tenant = models.ForeignKey("Tenant", related_name='subscriptions', blank=True, null=True)
    subscriber_user = models.ForeignKey("User", related_name='subscriptions', blank=True, null=True)
    service_specific_id = StrippedCharField(max_length=30, blank=True, null=True)
    service_specific_attribute = models.TextField(blank=True, null=True)
    connect_method = models.CharField(null=False, blank=False, max_length=30, choices=CONNECTIVITY_CHOICES, default="na")

    def __init__(self, *args, **kwargs):
        # for subclasses, set the default kind appropriately
        self._meta.get_field("kind").default = self.KIND
        super(Tenant, self).__init__(*args, **kwargs)

    def __unicode__(self):
        return u"%s-tenant-%s" % (str(self.kind), str(self.id))

    # helper for extracting things from a json-encoded service_specific_attribute
    def get_attribute(self, name, default=None):
        if self.service_specific_attribute:
            attributes = json.loads(self.service_specific_attribute)
        else:
            attributes = {}
        return attributes.get(name, default)

    def set_attribute(self, name, value):
        if self.service_specific_attribute:
            attributes = json.loads(self.service_specific_attribute)
        else:
            attributes = {}
        attributes[name]=value
        self.service_specific_attribute = json.dumps(attributes)

    @classmethod
    def get_tenant_objects(cls):
        return cls.objects.filter(kind = cls.KIND)

    @classmethod
    def get_deleted_tenant_objects(cls):
        return cls.deleted_objects.filter(kind = cls.KIND)

    # helper function to be used in subclasses that want to ensure service_specific_id is unique
    def validate_unique_service_specific_id(self):
        if self.pk is None:
            if self.service_specific_id is None:
                raise XOSMissingField("subscriber_specific_id is None, and it's a required field", fields={"service_specific_id": "cannot be none"})

            conflicts = self.get_tenant_objects().filter(service_specific_id=self.service_specific_id)
            if conflicts:
                raise XOSDuplicateKey("service_specific_id %s already exists" % self.service_specific_id, fields={"service_specific_id": "duplicate key"})

class CoarseTenant(Tenant):
    class Meta:
        proxy = True

    KIND = "coarse"

    def save(self, *args, **kwargs):
        if (not self.subscriber_service):
            raise XOSValidationError("subscriber_service cannot be null")
        if (self.subscriber_tenant or self.subscriber_user):
            raise XOSValidationError("subscriber_tenant and subscriber_user must be null")

        super(CoarseTenant,self).save()
