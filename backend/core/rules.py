"""帆布浸渍防水台业务规则。"""

from __future__ import annotations

from decimal import Decimal

from .models import ClothRoll, DipRun, Loft, ResinBand

MIN_CURE_HOURS_FOR_CURED = Decimal("12")


def latest_dip_run(roll: ClothRoll) -> DipRun | None:
    return roll.dip_runs.order_by("-started_at", "-id").first()


def enabled_resin_band(loft: Loft) -> ResinBand | None:
    """该帆布间现行启用的树脂浴浓度带；同间最多一条。"""
    return ResinBand.objects.filter(loft=loft, enabled=True).first()


def validate_resin_for_loft(loft: Loft, resin_pct: Decimal) -> tuple[bool, str]:
    """
    登记浸渍时核对树脂百分比：必须落在该间现行启用带的上下限之间（含边界）。
    无启用带同样不允许登记。
    """
    band = enabled_resin_band(loft)
    if band is None:
        return False, f"帆布间「{loft.name}」当前没有启用的树脂浴浓度带，不能登记浸渍"
    if resin_pct < band.lower_pct or resin_pct > band.upper_pct:
        return (
            False,
            f"树脂百分比 {resin_pct}% 超出帆布间「{loft.name}」现行浓度带 "
            f"{band.lower_pct}%~{band.upper_pct}%（含边界），不能登记浸渍",
        )
    return True, ""


def can_mark_roll_cured(roll: ClothRoll) -> tuple[bool, str]:
    """
    布卷转为「已固化」(cured) 的前提：
    最近一条浸渍记录的固化时长已记录，且 >= 12 小时。
    """
    latest = latest_dip_run(roll)
    if latest is None:
        return False, "该布卷尚无浸渍记录，不能标记为已固化"
    if latest.cure_hours is None:
        return False, "最近浸渍记录尚未填写固化时长，不能标记为已固化"
    if latest.cure_hours < MIN_CURE_HOURS_FOR_CURED:
        return (
            False,
            f"最近浸渍固化时长 {latest.cure_hours} 小时低于 {MIN_CURE_HOURS_FOR_CURED} 小时，不能标记为已固化",
        )
    return True, ""
