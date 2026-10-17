"""API views for DiagnoSure.

Endpoint map (matches the existing frontend fetch calls):
  POST   /api/user/                 register a user
  POST   /api/login/                authenticate, return public user data
  POST   /api/analyze/              run the disease-determination engine
  GET    /api/reports/<user_id>/    list a user's saved reports (history/diet)
  GET    /api/family/?user_id=..    list family members
  POST   /api/family/               add a family member
  DELETE /api/family/               remove a family member
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import AppUser, FamilyMember, Report
from .serializers import (
    AppUserSerializer, PublicUserSerializer,
    FamilyMemberSerializer, ReportSerializer,
)
from .engine.rag_engine import get_engine
from .engine.llm_explainer import generate_explanation


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@api_view(["POST"])
def register_user(request):
    serializer = AppUserSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def login_user(request):
    email = (request.data.get("email") or "").strip().lower()
    password = request.data.get("password") or ""
    try:
        user = AppUser.objects.get(email=email)
    except AppUser.DoesNotExist:
        return Response({"error": "Invalid email or password."},
                        status=status.HTTP_401_UNAUTHORIZED)
    if not user.check_password(password):
        return Response({"error": "Invalid email or password."},
                        status=status.HTTP_401_UNAUTHORIZED)
    return Response({"user": PublicUserSerializer(user).data})


# ---------------------------------------------------------------------------
# Core: disease determination
# ---------------------------------------------------------------------------
@api_view(["POST"])
def analyze(request):
    """Run the RAG engine over the reported symptoms and return ranked results.

    Accepts (all but `symptoms` optional):
      user_id, symptoms (str or list), severity, duration, medical_history,
      patient_name
    Returns a JSON array of up to 3 matches sorted by match % (descending);
    element [0] is the primary match.
    """
    data = request.data
    symptoms = data.get("symptoms", "")
    if isinstance(symptoms, list):
        symptoms = ", ".join(str(s) for s in symptoms)
    symptoms = (symptoms or "").strip()

    if not symptoms:
        return Response({"error": "No symptoms provided."},
                        status=status.HTTP_400_BAD_REQUEST)

    severity = (data.get("severity") or "").strip().lower() or None
    duration = (data.get("duration") or "").strip() or None
    medical_history = (data.get("medical_history") or "").strip()
    patient_name = (data.get("patient_name") or "").strip()

    engine = get_engine()
    results = engine.diagnose(
        symptoms_text=symptoms,
        severity=severity,
        duration=duration,
        medical_history=medical_history,
        top_k=3,
    )

    if not results:
        return Response([], status=status.HTTP_200_OK)

    # Top 3 suggestions, highest match % first.
    results = sorted(results, key=lambda r: r["score"], reverse=True)[:3]

    # Optional LLM rewrite of the top result's description (RAG generation step).
    top = results[0]
    llm_text = generate_explanation(
        symptoms, top["disease"], top["description"], top["precautions"]
    )
    if llm_text:
        top["description"] = llm_text

    # Persist the primary result so history/diet pages can read it back.
    user_id = data.get("user_id")
    if user_id:
        try:
            user = AppUser.objects.get(id=user_id)
            Report.objects.create(
                user=user,
                patient_name=patient_name or user.name,
                input_symptoms=symptoms,
                severity=severity or "",
                duration=duration or "",
                medical_history=medical_history,
                disease_name=top["disease"],
                score=top["score"],
                risk=top["risk"],
                description=top["description"],
                diet=top["diet"],
                specialist=top["specialist"],
                precautions=top["precautions"],
                matched_symptoms=top["matched_symptoms"],
            )
        except AppUser.DoesNotExist:
            pass  # anonymous assessment; just return the result

    return Response(results, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Reports (history + diet plan)
# ---------------------------------------------------------------------------
@api_view(["GET"])
def reports(request, user_id):
    qs = Report.objects.filter(user_id=user_id)  # already ordered newest-first
    return Response(ReportSerializer(qs, many=True).data)


# ---------------------------------------------------------------------------
# Family members
# ---------------------------------------------------------------------------
@api_view(["GET", "POST", "DELETE"])
def family(request):
    if request.method == "GET":
        user_id = request.query_params.get("user_id")
        qs = FamilyMember.objects.filter(user_id=user_id) if user_id else FamilyMember.objects.none()
        return Response(FamilyMemberSerializer(qs, many=True).data)

    if request.method == "POST":
        serializer = FamilyMemberSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # DELETE
    member_id = request.data.get("member_id")
    deleted, _ = FamilyMember.objects.filter(id=member_id).delete()
    if deleted:
        return Response({"status": "deleted"}, status=status.HTTP_200_OK)
    return Response({"error": "Member not found."}, status=status.HTTP_404_NOT_FOUND)
