"""帆布浸渍防水台业务规则。"""

from __future__ import annotations

from decimal import Decimal

from django.db import connection

from .models import ClothRoll, DipRun, Loft, ResinBand

MIN_CURE_HOURS_FOR_CURED = Decimal("12")


def latest_dip_run(roll: ClothRoll) -> DipRun | None:
    return roll.dip_runs.order_by("-started_at", "-id").first()


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


def active_resin_band(loft: Loft) -> ResinBand | None:
    """
    读取帆布间当前启用的浓度带；同间启用中最多一条（数据库唯一约束兜底）。
    处于事务中时以 select_for_update 锁定，与浓度带的启停/改限串行化。
    """
    qs = ResinBand.objects.filter(loft=loft, is_active=True)
    if connection.in_atomic_block:
        qs = qs.select_for_update()
    return qs.first()


def check_resin_pct_in_band(loft: Loft, resin_pct: Decimal) -> tuple[bool, str]:
    """
    登记浸渍前提：该帆布间存在启用中的浓度带，
    且树脂百分比落在 [下限, 上限] 闭区间内。
    """
    band = active_resin_band(loft)
    if band is None:
        return False, f"帆布间「{loft.name}」当前没有启用中的树脂浴浓度带，不能登记浸渍"
    if resin_pct < band.lower_pct or resin_pct > band.upper_pct:
        return (
            False,
            f"树脂百分比 {resin_pct}% 超出帆布间「{loft.name}」启用浓度带 "
            f"[{band.lower_pct}%, {band.upper_pct}%]，不能登记浸渍",
        )
    return True, ""
