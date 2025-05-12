from django.contrib import admin
from .models import User, Companies

class UserAdmin(admin.ModelAdmin):
    list_display=('id', 'username', 'first_name', 'last_name')

class CompaniesAdmin(admin.ModelAdmin):
    list_display=('id', 'name', 'description')
    list_editable=('name', 'description')


admin.site.register(User, UserAdmin)
admin.site.register(Companies, CompaniesAdmin)