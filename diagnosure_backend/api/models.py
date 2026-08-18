"""Database models for DiagnoSure.

Note on auth: to keep this aligned with the existing frontend (which posts a
plain name/email/password to /api/user/ and /api/login/), we use a simple
custom AppUser table with hashed passwords rather than Django's full auth user.
This is intentionally lightweight for a student project. For production you
would switch to Django's auth system + JWT (djangorestframework-simplejwt).
"""
from django.db import models
from django.contrib.auth.hashers import make_password, check_password


class AppUser(models.Model):
    GENDER_CHOICES = [("Male", "Male"), ("Female", "Female"), ("Other", "Other")]

    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)  # stored hashed
    age = models.PositiveIntegerField(default=0)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default="Other")
    created_at = models.DateTimeField(auto_now_add=True)

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.name} <{self.email}>"


class FamilyMember(models.Model):
    user = models.ForeignKey(
        AppUser, on_delete=models.CASCADE, related_name="family_members"
    )
    name = models.CharField(max_length=120)
    relation = models.CharField(max_length=60)
    age = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.relation})"


class Report(models.Model):
    """A stored assessment result, so history and diet pages can read it back."""
    user = models.ForeignKey(
        AppUser, on_delete=models.CASCADE, related_name="reports"
    )
    patient_name = models.CharField(max_length=120, blank=True)

    input_symptoms = models.TextField(blank=True)
    severity = models.CharField(max_length=20, blank=True)
    duration = models.CharField(max_length=20, blank=True)
    medical_history = models.CharField(max_length=255, blank=True)

    disease_name = models.CharField(max_length=120)
    score = models.FloatField(default=0)
    risk = models.CharField(max_length=20, default="Low")
    description = models.TextField(blank=True)
    diet = models.TextField(blank=True)
    specialist = models.CharField(max_length=120, blank=True)

    precautions = models.JSONField(default=list)
    matched_symptoms = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]  # newest first for history / latest diet

    def __str__(self):
        return f"{self.disease_name} for {self.user.name} ({self.risk})"
