from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import UserProfile


class UserProfileInline(admin.StackedInline[UserProfile, User]):
    model = UserProfile
    extra = 0
    fields = ("priority", "workos_user_id")
    readonly_fields = ("workos_user_id",)


class UserAdmin(BaseUserAdmin[User]):
    inlines = (UserProfileInline,)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
