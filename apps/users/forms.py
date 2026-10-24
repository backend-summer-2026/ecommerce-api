from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import User


class UserAdminCreationForm(UserCreationForm):
    """
    Form for creating new users via the Django admin interface.
    """

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'phone_number', 'role')

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
        return user


class UserAdminChangeForm(UserChangeForm):
    """
    Form for editing existing users via the Django admin interface.
    """

    class Meta:
        model = User
        fields = '__all__'
