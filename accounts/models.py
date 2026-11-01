from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()

# Create your models here.
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    full_name = models.CharField(max_length=50, blank=True, null=True)
    pronouns = models.CharField(max_length=4, blank=True, null=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    bio = models.CharField(max_length=160, blank=True, null=True)
    display_x_profile = models.BooleanField(default=False)

    def __str__(self):
        return self.full_name or self.user.username
    