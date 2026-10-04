from django.conf import settings
from django.db import models


class Loft(models.Model):
    name = models.CharField(max_length=120)
    location = models.CharField(max_length=200, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class ClothRoll(models.Model):
    STATUS_RAW = "raw"
    STATUS_DIPPING = "dipping"
    STATUS_CURED = "cured"
    STATUS_CHOICES = [
        (STATUS_RAW, "原布"),
        (STATUS_DIPPING, "浸渍中"),
        (STATUS_CURED, "已固化"),
    ]

    loft = models.ForeignKey(Loft, on_delete=models.CASCADE, related_name="rolls")
    roll_code = models.CharField(max_length=40)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RAW)
    fabric_weight_gsm = models.PositiveIntegerField(default=380)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["loft_id", "roll_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["loft", "roll_code"],
                name="uniq_roll_code_per_loft",
            )
        ]

    def __str__(self):
        return f"{self.loft.name}/{self.roll_code}"


class DipRun(models.Model):
    roll = models.ForeignKey(ClothRoll, on_delete=models.CASCADE, related_name="dip_runs")
    started_at = models.DateTimeField()
    resin_pct = models.DecimalField(max_digits=5, decimal_places=2)
    cure_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"Dip@{self.roll_id} {self.started_at}"


class ResinBand(models.Model):
    """帆布间树脂浴浓度带：登记浸渍时树脂百分比必须落在启用带内（含边界）。"""

    loft = models.ForeignKey(Loft, on_delete=models.CASCADE, related_name="resin_bands")
    lower_pct = models.DecimalField(max_digits=5, decimal_places=2)
    upper_pct = models.DecimalField(max_digits=5, decimal_places=2)
    is_active = models.BooleanField(default=False)
    configured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="resin_bands",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["loft_id", "-is_active", "-updated_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(lower_pct__lt=models.F("upper_pct")),
                name="resin_band_lower_lt_upper",
            ),
            models.CheckConstraint(
                check=models.Q(lower_pct__gt=0),
                name="resin_band_lower_positive",
            ),
            # 同一帆布间启用中的浓度带最多一条（数据库层兜底，并发也只留一版）
            models.UniqueConstraint(
                fields=["loft"],
                condition=models.Q(is_active=True),
                name="uniq_active_resin_band_per_loft",
            ),
        ]

    def __str__(self):
        state = "启用" if self.is_active else "停用"
        return f"{self.loft.name} [{self.lower_pct}%, {self.upper_pct}%] ({state})"
