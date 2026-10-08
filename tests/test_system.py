"""長者安心服務平台系統測試（以 Flask test client 進行整合測試）。

執行方式：python -m unittest tests.test_system -v
測試前會備份所有 JSON 資料檔，結束後自動還原，不影響既有資料。
"""
import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app as M  # noqa: E402

DATA_FILES = ["users.json", "help_requests.json", "services.json", "activities.json", "registrations.json",
              "attendances.json", "cases.json", "announcements.json", "contents.json", "welfare.json"]


class SystemTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backup = {}
        for f in DATA_FILES:
            p = ROOT / f
            cls.backup[f] = p.read_bytes() if p.exists() else None
        M.app.testing = True
        M.openai_client = None  # 測試 AI 備援流程，不呼叫外部 API
        M.create_user("t_user", "pass1234", "user")
        M.create_user("t_user2", "pass1234", "user")
        M.create_user("t_admin", "pass1234", "admin")
        services = M.load_services()
        services.append({"id": "svc-t1", "username": "t_admin", "service_name": "測試送餐（大安）", "description": "",
                         "service_type": "餐食協助", "target_group": "", "contact": "02-0000-0000",
                         "status": "開放申請", "district": "大安區", "service_scope": "本區", "created_at": ""})
        services.append({"id": "svc-t2", "username": "t_admin", "service_name": "測試全區送餐", "description": "",
                         "service_type": "餐食協助", "target_group": "", "contact": "", "status": "開放申請",
                         "district": "中正區", "service_scope": "全區", "created_at": ""})
        M.save_services(services)

    @classmethod
    def tearDownClass(cls):
        for f, data in cls.backup.items():
            p = ROOT / f
            if data is None:
                p.unlink(missing_ok=True)
            else:
                p.write_bytes(data)

    def client(self, username=None, role=None):
        c = M.app.test_client()
        if username:
            with c.session_transaction() as s:
                s["username"], s["role"] = username, role
        return c

    def new_activity(self, capacity=0, deadline="2099-12-31"):
        act = M.create_activity("t_admin", "測試活動", "", "其他", "2099-01-01", "2099-01-01", "里民活動中心",
                                capacity, deadline, "進行中")
        return act["id"]

    # ---------------- 會員與權限 ----------------
    def test_TC01_register_user(self):
        r = self.client().post("/register", data={"username": "t_new", "password": "abc123", "confirm_password": "abc123", "role": "user"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/user"))
        self.assertIsNotNone(M.find_user("t_new"))

    def test_TC02_register_duplicate(self):
        r = self.client().post("/register", data={"username": "t_user", "password": "x", "confirm_password": "x", "role": "user"})
        self.assertIn("此帳號已存在", r.get_data(as_text=True))

    def test_TC03_register_admin_wrong_code(self):
        r = self.client().post("/register", data={"username": "t_bad", "password": "x", "confirm_password": "x",
                                                  "role": "admin", "admin_code": "WRONG"})
        self.assertIn("管理者註冊代碼不正確", r.get_data(as_text=True))
        self.assertIsNone(M.find_user("t_bad"))

    def test_TC04_login_wrong_password(self):
        r = self.client().post("/login", data={"username": "t_user", "password": "wrong"})
        self.assertIn("帳號或密碼錯誤", r.get_data(as_text=True))

    def test_TC05_login_success_admin(self):
        r = self.client().post("/login", data={"username": "t_admin", "password": "pass1234"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/admin"))

    def test_TC06_role_protection(self):
        self.assertEqual(self.client().get("/user").status_code, 302)
        self.assertEqual(self.client("t_user", "user").get("/admin").status_code, 302)
        self.assertEqual(self.client("t_user", "user").get("/admin/proposal").status_code, 302)

    def test_TC07_profile_required_fields(self):
        r = self.client("t_user", "user").post("/user/profile", data={"contact_name": "王小明"})
        self.assertIn("請填寫聯絡人姓名、手機、長者姓名與所在區域", r.get_data(as_text=True))

    def test_TC08_profile_saved_and_prefilled(self):
        c = self.client("t_user", "user")
        c.post("/user/profile", data={"contact_name": "王小明", "phone": "0912345678", "elder_name": "王阿嬤",
                                      "district": "大安區", "household_status": "獨居", "care_notes": "使用助行器"})
        form = c.get("/user/help-request").get_data(as_text=True)
        self.assertIn('value="王阿嬤"', form)
        self.assertIn('value="大安區" selected', form)

    def test_TC09_change_password_wrong_current(self):
        before = M.find_user("t_user2")["password"]
        r = self.client("t_user2", "user").post("/user/profile", data={"action": "password", "current_password": "nope",
                                                                         "new_password": "abcdef", "confirm_password": "abcdef"})
        self.assertIn("目前密碼不正確", r.get_data(as_text=True))
        self.assertEqual(before, M.find_user("t_user2")["password"])

    # ---------------- 長者需求與媒合 ----------------
    def test_TC10_help_request_required(self):
        r = self.client("t_user", "user").post("/user/help-request", data={"need_type": "餐食協助"})
        self.assertIn("請填寫需求類型、時間、地點與所在區域", r.get_data(as_text=True))

    def test_TC11_help_request_created(self):
        r = self.client("t_user", "user").post("/user/help-request", data={
            "need_type": "餐食協助", "need_when": "週一中午", "location": "家中", "district": "大安區"})
        self.assertIn("/user/service-matches?request_id=", r.headers["Location"])
        rid = r.headers["Location"].split("request_id=")[1]
        self.assertEqual(M.get_help_request(rid)["status"], "待處理")

    def test_TC12_matching_filters_type_and_area(self):
        names = [m["service"]["service_name"] for m in M.get_help_request_matches({"need_type": "餐食協助", "district": "大安區"})]
        self.assertEqual(names[0], "測試送餐（大安）")          # 同區優先
        self.assertIn("測試全區送餐", names)                    # 全區皆可服務
        self.assertNotIn("餐食配送服務", names)                  # 中山區且僅服務本區：不推薦
        self.assertNotIn("就醫接送服務", names)                  # 類型不符：不推薦

    def test_TC13_other_user_cannot_view_request(self):
        req = M.create_help_request("t_user", "餐食協助", "週二", "家中", "1 小時", district="大安區")
        r = self.client("t_user2", "user").get(f"/user/service-matches?request_id={req['id']}")
        self.assertEqual(r.status_code, 302)

    def test_TC14_apply_service(self):
        req = M.create_help_request("t_user", "餐食協助", "週三", "家中", "1 小時", district="大安區")
        self.client("t_user", "user").post(f"/user/help-requests/{req['id']}/apply/svc-t1")
        self.assertEqual(M.get_help_request(req["id"])["status"], "已申請")

    def test_TC15_admin_update_status_history(self):
        req = M.create_help_request("t_user", "餐食協助", "週四", "家中", "1 小時", district="大安區")
        self.client("t_admin", "admin").post(f"/admin/help-requests/{req['id']}/status",
                                             data={"status": "已安排", "assigned_unit": "測試送餐（大安）", "admin_note": "週四送達"})
        item = M.get_help_request(req["id"])
        self.assertEqual(item["status"], "已安排")
        self.assertIn("已安排", item["history"][0]["message"])

    def test_TC16_service_type_required(self):
        self.client("t_admin", "admin").post("/admin/services/create", data={"service_name": "無類型服務", "service_type": ""})
        self.assertFalse(any(s["service_name"] == "無類型服務" for s in M.load_services()))

    # ---------------- 里民活動 ----------------
    def test_TC17_register_activity(self):
        aid = self.new_activity()
        r = self.client("t_user", "user").post(f"/user/activities/{aid}/register", data={"phone": "0912"}, follow_redirects=True)
        self.assertIn("待管理者審核", r.get_data(as_text=True))

    def test_TC18_duplicate_registration_blocked(self):
        aid = self.new_activity()
        c = self.client("t_user", "user")
        c.post(f"/user/activities/{aid}/register")
        r = c.post(f"/user/activities/{aid}/register", follow_redirects=True)
        self.assertIn("您已報名此活動", r.get_data(as_text=True))

    def test_TC19_checkin_requires_approval(self):
        aid = self.new_activity()
        c = self.client("t_user", "user")
        c.post(f"/user/activities/{aid}/register")
        r = c.post(f"/user/activities/{aid}/checkin", follow_redirects=True)
        self.assertIn("報名審核通過後才可簽到", r.get_data(as_text=True))

    def test_TC20_checkin_after_approval_once(self):
        aid = self.new_activity()
        c = self.client("t_user", "user")
        c.post(f"/user/activities/{aid}/register")
        reg = M.get_user_registration(aid, "t_user")
        self.client("t_admin", "admin").post(f"/admin/registrations/{reg['id']}/approve")
        self.assertIn("簽到成功", c.post(f"/user/activities/{aid}/checkin", follow_redirects=True).get_data(as_text=True))
        self.assertIn("您已完成簽到", c.post(f"/user/activities/{aid}/checkin", follow_redirects=True).get_data(as_text=True))
        page = self.client("t_admin", "admin").get(f"/admin/activities/{aid}/attendance").get_data(as_text=True)
        self.assertIn("t_user", page)

    def test_TC21_capacity_full(self):
        aid = self.new_activity(capacity=1)
        self.client("t_user", "user").post(f"/user/activities/{aid}/register")
        r = self.client("t_user2", "user").post(f"/user/activities/{aid}/register", follow_redirects=True)
        self.assertIn("報名人數已額滿", r.get_data(as_text=True))

    # ---------------- 長者福利資訊 ----------------
    def test_TC22_welfare_search(self):
        page = self.client("t_user", "user").get("/welfare?q=假牙").get_data(as_text=True)
        self.assertIn("老人假牙補助", page)
        self.assertNotIn("敬老卡", page)

    def test_TC23_welfare_assistant_fallback(self):
        r = self.client("t_user", "user").post("/api/welfare-chat", json={"message": "我媽媽行動不便需要人照顧"})
        self.assertIn("長期照顧服務", r.get_json()["reply"])

    def test_TC24_admin_create_welfare(self):
        before = len(M.load_welfare())
        self.client("t_admin", "admin").post("/admin/welfare/create", data={
            "title": "測試福利", "category": "其他", "eligibility": "65 歲以上", "apply_method": "洽里辦公處"})
        self.assertEqual(len(M.load_welfare()), before + 1)

    def test_TC25_proposal_admin_only(self):
        self.assertEqual(self.client("t_admin", "admin").get("/admin/proposal").status_code, 200)
        self.assertEqual(self.client("t_user", "user").post("/api/welfare-chat", json={"message": ""}).status_code, 200)
        self.assertEqual(self.client("t_admin", "admin").post("/api/welfare-chat", json={"message": "x"}).status_code, 403)


if __name__ == "__main__":
    unittest.main(verbosity=2)
