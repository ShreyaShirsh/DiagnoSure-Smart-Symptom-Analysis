from rest_framework import serializers
from .models import AppUser, FamilyMember, Report


class AppUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppUser
        fields = ["id", "name", "email", "password", "age", "gender", "created_at"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        raw = validated_data.pop("password")
        user = AppUser(**validated_data)
        user.set_password(raw)
        user.save()
        return user


class PublicUserSerializer(serializers.ModelSerializer):
    """User data safe to return to the client (never the password)."""
    class Meta:
        model = AppUser
        fields = ["id", "name", "email", "age", "gender"]


class FamilyMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamilyMember
        fields = ["id", "user", "name", "relation", "age", "created_at"]


class ReportSerializer(serializers.ModelSerializer):
    # Expose both keys the frontend uses across pages.
    disease = serializers.CharField(source="disease_name", read_only=True)
    created_at = serializers.DateTimeField(format="%d %b %Y, %I:%M %p", read_only=True)

    class Meta:
        model = Report
        fields = [
            "id", "disease", "disease_name", "score", "risk", "description",
            "diet", "specialist", "precautions", "matched_symptoms",
            "input_symptoms", "severity", "duration", "created_at",
        ]
