from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.db import transaction

class Command(BaseCommand):
    help = 'Create or refresh recommended staff roles without creating accounts or passwords.'
    @transaction.atomic
    def handle(self,*args,**options):
        roles = {
            'Project Manager': {'state','city','area','project','projectlayout','plot','amenity','projectimage','gallerycategory'},
            'Sales Manager': {'enquiry','plot'},
            'Content Editor': {'sitesettings','service','herobanner','announcement','article','page','testimonial','projectimage','gallerycategory','sociallink','homepagesection','verifiedstatistic'},
        }
        for name,models in roles.items():
            group,_ = Group.objects.get_or_create(name=name)
            permissions = Permission.objects.filter(content_type__app_label='estate',content_type__model__in=models)
            if name == 'Sales Manager':
                permissions=permissions.exclude(codename__in=['add_plot','delete_plot'])
            group.permissions.set(permissions)
            audit = Permission.objects.filter(content_type__app_label='estate',codename='view_plotstatushistory')
            if name in {'Project Manager','Sales Manager'}:group.permissions.add(*audit)
            self.stdout.write(self.style.SUCCESS(f'{name}: permissions refreshed'))
        self.stdout.write('Assign these groups to active staff users in Company administration → Users. No accounts were created.')
