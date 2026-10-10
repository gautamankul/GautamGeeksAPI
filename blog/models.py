from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()

# Create your models here.
class Category(models.Model):
    name = models.CharField(max_length=255, blank=True, default='')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='category_created')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='category_updated')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name or f"Untitled Category #{self.id}"
    
class Post(models.Model):
    title = models.CharField(max_length=255, blank=True, default='')
    content_json = models.JSONField(null=True, blank=True)
    content_html = models.TextField(blank=True, default='')
    is_draft = models.BooleanField(default=True)
    is_published = models.BooleanField(default=False)
    category = models.ForeignKey(Category,on_delete=models.SET_NULL,null=True,blank=True,related_name="posts")
    created_by = models.ForeignKey(User,on_delete=models.CASCADE,related_name='posts_created')
    updated_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name='posts_updated')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title or f"Untitled Post #{self.id}"
    
    def save(self, *args, **kwargs):
        self.is_published = True
        self.is_draft = False
        super().save(*args, **kwargs)
