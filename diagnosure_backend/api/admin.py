from django.contrib import admin
from .models import AppUser, FamilyMember, Report

admin.site.register(AppUser)
admin.site.register(FamilyMember)
admin.site.register(Report)
