from decimal import Decimal

from rest_framework import serializers

from .models import ClothRoll, DipRun, Loft, ResinBand
from .rules import can_mark_roll_cured, validate_resin_for_loft


class LoftSerializer(serializers.ModelSerializer):
    rollCount = serializers.SerializerMethodField()

    class Meta:
        model = Loft
        fields = ("id", "name", "location", "notes", "rollCount", "created_at")
        read_only_fields = ("id", "rollCount", "created_at")

    def get_rollCount(self, obj):
        if hasattr(obj, "roll_count"):
            return obj.roll_count
        return obj.rolls.count()


class ClothRollSerializer(serializers.ModelSerializer):
    loftId = serializers.PrimaryKeyRelatedField(source="loft", queryset=Loft.objects.all())
    rollCode = serializers.CharField(source="roll_code")
    fabricWeightGsm = serializers.IntegerField(source="fabric_weight_gsm", required=False)
    loftName = serializers.CharField(source="loft.name", read_only=True)

    class Meta:
        model = ClothRoll
        fields = (
            "id",
            "loftId",
            "loftName",
            "rollCode",
            "status",
            "fabricWeightGsm",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "loftName", "created_at", "updated_at")

    def validate(self, attrs):
        loft = attrs.get("loft") or getattr(self.instance, "loft", None)
        roll_code = attrs.get("roll_code") or getattr(self.instance, "roll_code", None)
        if loft and roll_code:
            qs = ClothRoll.objects.filter(loft=loft, roll_code=roll_code)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"rollCode": "同一帆布间卷号必须唯一"})

        new_status = attrs.get("status")
        if new_status == ClothRoll.STATUS_CURED:
            roll = self.instance
            if roll is None:
                raise serializers.ValidationError(
                    {"status": "新建布卷不能直接设为已固化"}
                )
            # 合并未提交字段到临时视角：用当前实例校验
            ok, msg = can_mark_roll_cured(roll)
            if not ok:
                raise serializers.ValidationError({"status": msg})
        return attrs


class DipRunSerializer(serializers.ModelSerializer):
    rollId = serializers.PrimaryKeyRelatedField(
        source="roll", queryset=ClothRoll.objects.all()
    )
    startedAt = serializers.DateTimeField(source="started_at")
    resinPct = serializers.DecimalField(source="resin_pct", max_digits=5, decimal_places=2)
    cureHours = serializers.DecimalField(
        source="cure_hours",
        max_digits=6,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    rollCode = serializers.CharField(source="roll.roll_code", read_only=True)
    loftName = serializers.CharField(source="roll.loft.name", read_only=True)

    class Meta:
        model = DipRun
        fields = (
            "id",
            "rollId",
            "rollCode",
            "loftName",
            "startedAt",
            "resinPct",
            "cureHours",
            "notes",
            "created_at",
        )
        read_only_fields = ("id", "rollCode", "loftName", "created_at")

    def validate(self, attrs):
        # 仅登记（新建）时核对树脂浴浓度带；固化标记/卷态变更不走这里。
        if self.instance is None:
            roll = attrs.get("roll")
            resin_pct = attrs.get("resin_pct")
            if roll is not None and resin_pct is not None:
                ok, msg = validate_resin_for_loft(roll.loft, resin_pct)
                if not ok:
                    raise serializers.ValidationError({"resinPct": msg})
        return attrs


class ResinBandSerializer(serializers.ModelSerializer):
    loftId = serializers.PrimaryKeyRelatedField(source="loft", queryset=Loft.objects.all())
    lowerPct = serializers.DecimalField(
        source="lower_pct", max_digits=5, decimal_places=2
    )
    upperPct = serializers.DecimalField(
        source="upper_pct", max_digits=5, decimal_places=2
    )
    loftName = serializers.CharField(source="loft.name", read_only=True)
    createdByUsername = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = ResinBand
        fields = (
            "id",
            "loftId",
            "loftName",
            "lowerPct",
            "upperPct",
            "enabled",
            "createdByUsername",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "loftName", "createdByUsername", "created_at", "updated_at")

    def validate(self, attrs):
        lower = attrs.get("lower_pct")
        if lower is None and self.instance is not None:
            lower = self.instance.lower_pct
        upper = attrs.get("upper_pct")
        if upper is None and self.instance is not None:
            upper = self.instance.upper_pct

        if lower is not None and lower <= Decimal("0"):
            raise serializers.ValidationError({"lowerPct": "下限百分必须为正数"})
        if upper is not None and upper <= Decimal("0"):
            raise serializers.ValidationError({"upperPct": "上限百分必须为正数"})
        if lower is not None and upper is not None and lower >= upper:
            raise serializers.ValidationError({"lowerPct": "下限百分必须小于上限百分"})

        loft = attrs.get("loft") or getattr(self.instance, "loft", None)
        enabled = attrs.get("enabled")
        if enabled is None:
            enabled = self.instance.enabled if self.instance is not None else True
        # 友好预检：同间已有启用带时直接中文拦下；并发竞争仍由数据库唯一约束兜底。
        if enabled and loft is not None:
            qs = ResinBand.objects.filter(loft=loft, enabled=True)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"enabled": f"帆布间「{loft.name}」已有启用中的浓度带，同间最多启用一条"}
                )
        return attrs
