import re
from datetime import date
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Enquiry, Project, Plot

class EnquiryForm(forms.ModelForm):
    website = forms.CharField(required=False, widget=forms.HiddenInput)
    consent = forms.BooleanField(required=True, label='I agree to be contacted about my enquiry.')
    class Meta:
        model = Enquiry
        fields = ['name','email','phone','message','project','plot','kind','preferred_date','consent']
        widgets = {'message': forms.Textarea(attrs={'rows':4}), 'preferred_date':forms.DateInput(attrs={'type':'date'})}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['project'].queryset = Project.public.all()
        self.fields['plot'].queryset = Plot.objects.filter(project__status='published',project__area__active=True,layout__active=True,layout__is_draft=False).exclude(status='hidden')
    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        digits = re.sub(r'\D','',phone)
        if not 10 <= len(digits) <= 15:
            raise ValidationError('Enter a valid phone number with 10–15 digits.')
        return phone
    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if len(name) < 2: raise ValidationError('Please enter your full name.')
        return name
    def clean_message(self):
        message = self.cleaned_data.get('message','').strip()
        if len(message) > 5000: raise ValidationError('Please keep your message within 5,000 characters.')
        return message
    def clean(self):
        data = super().clean()
        if data.get('website'): raise ValidationError('Unable to submit this enquiry.')
        if data.get('preferred_date') and data['preferred_date'] < timezone.localdate():
            self.add_error('preferred_date','Please select today or a future date.')
        if data.get('kind') == Enquiry.Kind.SITE_VISIT and not data.get('preferred_date'):
            self.add_error('preferred_date','Choose your preferred visit date.')
        if data.get('plot') and data.get('project') != data['plot'].project:
            self.add_error('plot','Choose a plot in the selected project.')
        return data
