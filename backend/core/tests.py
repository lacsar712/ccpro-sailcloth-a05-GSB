import threading
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import ClothRoll, DipRun, Loft, ResinBand

User = get_user_model()


def make_user(username, role):
    return User.objects.create_user(username=username, password="pw123456", role=role)


def make_loft(name="北岸帆布间"):
    return Loft.objects.create(name=name, location="港区二号库")


def make_roll(loft, code="R-01", status=ClothRoll.STATUS_RAW):
    return ClothRoll.objects.create(loft=loft, roll_code=code, status=status)


def make_band(loft, admin, lower="20.00", upper="30.00", active=True):
    return ResinBand.objects.create(
        loft=loft,
        lower_pct=Decimal(lower),
        upper_pct=Decimal(upper),
        is_active=active,
        configured_by=admin,
    )


def dip_payload(roll, resin_pct, cure_hours=None):
    return {
        "rollId": roll.id,
        "startedAt": timezone.now().isoformat(),
        "resinPct": str(resin_pct),
        "cureHours": cure_hours,
        "notes": "",
    }


class BandPermissionTests(TestCase):
    """仅管理员可改带与启停；操作工只读。"""

    def setUp(self):
        self.admin = make_user("admin", User.ROLE_ADMIN)
        self.worker = make_user("worker", User.ROLE_WORKER)
        self.loft = make_loft()
        self.band = make_band(self.loft, self.admin)

    def auth_client(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def test_worker_can_list_bands(self):
        resp = self.auth_client(self.worker).get("/api/bands/")
        self.assertEqual(resp.status_code, 200)

    def test_worker_cannot_create_band(self):
        resp = self.auth_client(self.worker).post(
            "/api/bands/",
            {"loftId": self.loft.id, "lowerPct": "10", "upperPct": "15", "isActive": False},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(ResinBand.objects.count(), 1)

    def test_worker_cannot_update_limits(self):
        resp = self.auth_client(self.worker).patch(
            f"/api/bands/{self.band.id}/", {"lowerPct": "5"}, format="json"
        )
        self.assertEqual(resp.status_code, 403)
        self.band.refresh_from_db()
        self.assertEqual(self.band.lower_pct, Decimal("20.00"))

    def test_worker_cannot_toggle_active(self):
        resp = self.auth_client(self.worker).patch(
            f"/api/bands/{self.band.id}/", {"isActive": False}, format="json"
        )
        self.assertEqual(resp.status_code, 403)
        self.band.refresh_from_db()
        self.assertTrue(self.band.is_active)

    def test_unauthenticated_rejected(self):
        resp = APIClient().get("/api/bands/")
        self.assertEqual(resp.status_code, 401)


class BandValidationTests(TestCase):
    """下限须小于上限，二者都须为正；同间启用中最多一条。"""

    def setUp(self):
        self.admin = make_user("admin", User.ROLE_ADMIN)
        self.loft = make_loft()
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def post_band(self, **kw):
        payload = {
            "loftId": self.loft.id,
            "lowerPct": "20",
            "upperPct": "30",
            "isActive": False,
        }
        payload.update(kw)
        return self.client.post("/api/bands/", payload, format="json")

    def test_lower_must_be_less_than_upper(self):
        resp = self.post_band(lowerPct="30", upperPct="20")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(ResinBand.objects.count(), 0)

    def test_lower_equal_upper_rejected(self):
        resp = self.post_band(lowerPct="25", upperPct="25")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(ResinBand.objects.count(), 0)

    def test_limits_must_be_positive(self):
        resp = self.post_band(lowerPct="0", upperPct="20")
        self.assertEqual(resp.status_code, 400)
        resp = self.post_band(lowerPct="-5", upperPct="20")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(ResinBand.objects.count(), 0)

    def test_create_records_configured_by(self):
        resp = self.post_band(isActive=True)
        self.assertEqual(resp.status_code, 201)
        band = ResinBand.objects.get()
        self.assertEqual(band.configured_by, self.admin)
        self.assertEqual(resp.data["configuredBy"], "admin")

    def test_second_active_band_same_loft_rejected(self):
        make_band(self.loft, self.admin, active=True)
        resp = self.post_band(lowerPct="10", upperPct="15", isActive=True)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("启用", str(resp.data))
        self.assertEqual(ResinBand.objects.filter(is_active=True).count(), 1)

    def test_second_inactive_band_allowed(self):
        make_band(self.loft, self.admin, active=True)
        resp = self.post_band(lowerPct="10", upperPct="15", isActive=False)
        self.assertEqual(resp.status_code, 201)

    def test_enable_second_band_rejected_until_first_disabled(self):
        band_a = make_band(self.loft, self.admin, active=True)
        band_b = make_band(self.loft, self.admin, "10", "15", active=False)
        resp = self.client.patch(
            f"/api/bands/{band_b.id}/", {"isActive": True}, format="json"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(ResinBand.objects.filter(is_active=True).count(), 1)
        # 停用 A 后可以启用 B
        resp = self.client.patch(
            f"/api/bands/{band_a.id}/", {"isActive": False}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        resp = self.client.patch(
            f"/api/bands/{band_b.id}/", {"isActive": True}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ResinBand.objects.filter(is_active=True).count(), 1)
        self.assertTrue(ResinBand.objects.get(pk=band_b.pk).is_active)

    def test_admin_can_update_limits(self):
        band = make_band(self.loft, self.admin, active=True)
        resp = self.client.patch(
            f"/api/bands/{band.id}/",
            {"lowerPct": "22", "upperPct": "28"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        band.refresh_from_db()
        self.assertEqual(band.lower_pct, Decimal("22"))
        self.assertEqual(band.upper_pct, Decimal("28"))

    def test_db_constraint_blocks_duplicate_active_even_bypassing_api(self):
        make_band(self.loft, self.admin, active=True)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ResinBand.objects.create(
                    loft=self.loft,
                    lower_pct=Decimal("5"),
                    upper_pct=Decimal("9"),
                    is_active=True,
                    configured_by=self.admin,
                )
        self.assertEqual(
            ResinBand.objects.filter(loft=self.loft, is_active=True).count(), 1
        )


class DipBandRuleTests(TestCase):
    """登记浸渍必须落在启用带内（含边界）；无启用带挡住；出带不半插入。"""

    def setUp(self):
        self.admin = make_user("admin", User.ROLE_ADMIN)
        self.worker = make_user("worker", User.ROLE_WORKER)
        self.loft = make_loft()
        self.roll = make_roll(self.loft)
        self.band = make_band(self.loft, self.admin, "20.00", "30.00", active=True)
        self.client = APIClient()
        self.client.force_authenticate(self.worker)

    def post_dip(self, resin_pct, cure_hours=None):
        return self.client.post(
            "/api/dips/", dip_payload(self.roll, resin_pct, cure_hours), format="json"
        )

    def test_in_band_accepted(self):
        resp = self.post_dip("25")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(DipRun.objects.count(), 1)

    def test_boundaries_inclusive(self):
        self.assertEqual(self.post_dip("20").status_code, 201)
        self.assertEqual(self.post_dip("30").status_code, 201)
        self.assertEqual(DipRun.objects.count(), 2)

    def test_below_band_blocked_chinese_and_no_partial_insert(self):
        resp = self.post_dip("19.99")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("不能登记浸渍", str(resp.data))
        self.assertEqual(DipRun.objects.count(), 0)
        self.roll.refresh_from_db()
        self.assertEqual(self.roll.status, ClothRoll.STATUS_RAW)

    def test_above_band_blocked(self):
        resp = self.post_dip("30.01")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(DipRun.objects.count(), 0)

    def test_no_active_band_blocked(self):
        self.band.is_active = False
        self.band.save()
        resp = self.post_dip("25")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("没有启用中的树脂浴浓度带", str(resp.data))
        self.assertEqual(DipRun.objects.count(), 0)

    def test_no_band_at_all_blocked(self):
        loft2 = make_loft("南岸帆布间")
        roll2 = make_roll(loft2, "R-99")
        resp = self.client.post(
            "/api/dips/", dip_payload(roll2, "25"), format="json"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(DipRun.objects.count(), 0)

    def test_band_checked_against_rolls_own_loft(self):
        loft2 = make_loft("南岸帆布间")
        make_band(loft2, self.admin, "40.00", "50.00", active=True)
        roll2 = make_roll(loft2, "R-99")
        resp = self.client.post(
            "/api/dips/", dip_payload(roll2, "25"), format="json"
        )
        self.assertEqual(resp.status_code, 400)
        resp = self.client.post(
            "/api/dips/", dip_payload(roll2, "45"), format="json"
        )
        self.assertEqual(resp.status_code, 201)

    def test_worker_can_register_dip(self):
        # 操作工可登记浸渍（带内）
        resp = self.post_dip("25")
        self.assertEqual(resp.status_code, 201)


class RollStatusRuleTests(TestCase):
    """标已固化与改卷态不看浓度带；12 小时旧规则照旧。"""

    def setUp(self):
        self.admin = make_user("admin", User.ROLE_ADMIN)
        self.loft = make_loft()
        self.roll = make_roll(self.loft, status=ClothRoll.STATUS_DIPPING)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_status_change_ignores_band(self):
        # 该间没有任何浓度带，改卷态照常
        resp = self.client.patch(
            f"/api/rolls/{self.roll.id}/", {"status": "raw"}, format="json"
        )
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_cured_rule_still_enforced(self):
        DipRun.objects.create(
            roll=self.roll,
            started_at=timezone.now(),
            resin_pct=Decimal("25"),
            cure_hours=Decimal("4"),
        )
        resp = self.client.patch(
            f"/api/rolls/{self.roll.id}/", {"status": "cured"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)
        DipRun.objects.create(
            roll=self.roll,
            started_at=timezone.now(),
            resin_pct=Decimal("25"),
            cure_hours=Decimal("12"),
        )
        resp = self.client.patch(
            f"/api/rolls/{self.roll.id}/", {"status": "cured"}, format="json"
        )
        self.assertEqual(resp.status_code, 200, resp.data)


class ConcurrencyTests(TransactionTestCase):
    """两名管理员抢着改同一间启用带：库里只留一版；随后出带登记被挡。"""

    def setUp(self):
        self.admin_a = make_user("admin_a", User.ROLE_ADMIN)
        self.admin_b = make_user("admin_b", User.ROLE_ADMIN)
        self.loft = make_loft()

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def _run_concurrently(self, fn_a, fn_b):
        # sqlite 共享缓存模式不支持并发写（表级锁直接报错），
        # 退化为顺序执行——不变量断言不变；PostgreSQL 上走真实并发。
        if connection.vendor == "sqlite":
            return {"a": fn_a(), "b": fn_b()}
        results = {}
        barrier = threading.Barrier(2)

        def wrap(key, fn):
            def run():
                barrier.wait(timeout=10)
                results[key] = fn()

            return threading.Thread(target=run)

        t1, t2 = wrap("a", fn_a), wrap("b", fn_b)
        t1.start()
        t2.start()
        t1.join(30)
        t2.join(30)
        return results

    def test_concurrent_enable_leaves_single_active_band(self):
        band_a = make_band(self.loft, self.admin_a, "10.00", "20.00", active=False)
        band_b = make_band(self.loft, self.admin_b, "30.00", "40.00", active=False)

        def enable(user, band_id):
            def fn():
                return self._client(user).patch(
                    f"/api/bands/{band_id}/", {"isActive": True}, format="json"
                )

            return fn

        results = self._run_concurrently(
            enable(self.admin_a, band_a.id), enable(self.admin_b, band_b.id)
        )
        statuses = sorted(r.status_code for r in results.values())
        self.assertEqual(statuses, [200, 400], statuses)
        self.assertEqual(
            ResinBand.objects.filter(loft=self.loft, is_active=True).count(), 1
        )

    def test_concurrent_limit_updates_leave_single_version_then_out_of_band_blocked(self):
        band = make_band(self.loft, self.admin_a, "20.00", "30.00", active=True)
        roll = make_roll(self.loft)

        def set_limits(user, lower, upper):
            def fn():
                return self._client(user).patch(
                    f"/api/bands/{band.id}/",
                    {"lowerPct": lower, "upperPct": upper},
                    format="json",
                )

            return fn

        results = self._run_concurrently(
            set_limits(self.admin_a, "10", "20"),
            set_limits(self.admin_b, "30", "40"),
        )
        for r in results.values():
            self.assertEqual(r.status_code, 200, r.data)

        # 库里只留一版：同一行，上下限必为其中一套，不得混杂
        self.assertEqual(ResinBand.objects.filter(loft=self.loft).count(), 1)
        band.refresh_from_db()
        final = (str(band.lower_pct), str(band.upper_pct))
        self.assertIn(final, {("10.00", "20.00"), ("30.00", "40.00")})

        # 随后用出带树脂（25 对两套限都在带外）登记必须被挡
        resp = self._client(self.admin_a).post(
            "/api/dips/", dip_payload(roll, "25"), format="json"
        )
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(DipRun.objects.count(), 0)


class SeedDataTests(TestCase):
    def test_seed_creates_active_band_and_raw_roll(self):
        call_command("seed_data")
        loft = Loft.objects.get(name="北岸帆布间")
        band = ResinBand.objects.get(loft=loft, is_active=True)
        self.assertEqual(band.lower_pct, Decimal("20.00"))
        self.assertEqual(band.upper_pct, Decimal("30.00"))
        self.assertEqual(band.configured_by.username, "admin")
        rolls = ClothRoll.objects.filter(loft=loft)
        self.assertEqual(rolls.count(), 1)
        self.assertEqual(rolls.first().status, ClothRoll.STATUS_RAW)
