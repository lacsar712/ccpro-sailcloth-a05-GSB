from django.db import IntegrityError, transaction
from django.db.models import Count
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ClothRoll, DipRun, Loft, ResinBand
from .permissions import IsAdminRole
from .serializers import (
    ClothRollSerializer,
    DipRunSerializer,
    LoftSerializer,
    ResinBandSerializer,
)

ACTIVE_BAND_CONFLICT_MSG = "该帆布间已存在启用中的浓度带，本次保存未生效"


class LoftViewSet(viewsets.ModelViewSet):
    queryset = Loft.objects.annotate(roll_count=Count("rolls")).all()
    serializer_class = LoftSerializer


class ClothRollViewSet(viewsets.ModelViewSet):
    serializer_class = ClothRollSerializer

    def get_queryset(self):
        qs = ClothRoll.objects.select_related("loft").all()
        loft_id = self.request.query_params.get("loftId")
        status = self.request.query_params.get("status")
        if loft_id:
            qs = qs.filter(loft_id=loft_id)
        if status:
            qs = qs.filter(status=status)
        return qs


class DipRunViewSet(viewsets.ModelViewSet):
    serializer_class = DipRunSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = DipRun.objects.select_related("roll", "roll__loft").all()
        roll_id = self.request.query_params.get("rollId")
        if roll_id:
            qs = qs.filter(roll_id=roll_id)
        return qs

    def create(self, request, *args, **kwargs):
        # 事务内校验并写入：读取启用浓度带时加行锁，
        # 与管理员改带/启停串行化；校验不过则整体不落库（无半插入）。
        with transaction.atomic():
            return super().create(request, *args, **kwargs)


class ResinBandViewSet(viewsets.ModelViewSet):
    """树脂浴浓度带：任何登录用户可读；新建/改限/启停仅管理员。"""

    serializer_class = ResinBandSerializer

    def get_queryset(self):
        qs = ResinBand.objects.select_related("loft", "configured_by").all()
        loft_id = self.request.query_params.get("loftId")
        if loft_id:
            qs = qs.filter(loft_id=loft_id)
        return qs

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAdminRole()]

    def create(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                return super().create(request, *args, **kwargs)
        except IntegrityError:
            # 数据库唯一约束兜底：并发启用同间浓度带时只留一版
            raise ValidationError({"isActive": ACTIVE_BAND_CONFLICT_MSG})

    def update(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                return super().update(request, *args, **kwargs)
        except IntegrityError:
            raise ValidationError({"isActive": ACTIVE_BAND_CONFLICT_MSG})

    def perform_create(self, serializer):
        self._guard_single_active(serializer)
        serializer.save(configured_by=self.request.user)

    def perform_update(self, serializer):
        self._guard_single_active(serializer)
        serializer.save()

    def _guard_single_active(self, serializer):
        """启用前在事务内锁定该间全部浓度带，确认无其他启用中的带。"""
        instance = serializer.instance
        data = serializer.validated_data
        effective_active = data.get(
            "is_active", getattr(instance, "is_active", False)
        )
        loft = data.get("loft", getattr(instance, "loft", None))
        if not effective_active or loft is None:
            return
        qs = ResinBand.objects.select_for_update().filter(loft=loft, is_active=True)
        if instance is not None:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise ValidationError({"isActive": ACTIVE_BAND_CONFLICT_MSG})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    data = {
        "loftCount": Loft.objects.count(),
        "rawRollCount": ClothRoll.objects.filter(status=ClothRoll.STATUS_RAW).count(),
        "dippingRollCount": ClothRoll.objects.filter(
            status=ClothRoll.STATUS_DIPPING
        ).count(),
        "curedRollCount": ClothRoll.objects.filter(status=ClothRoll.STATUS_CURED).count(),
        "dipRunCount": DipRun.objects.count(),
    }
    return Response(data)
