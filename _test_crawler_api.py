import json
import re
from crawler import create_session, warm_up_session, post_form, CHECK_MONTH_URL, GET_FUNDS_LIST_URL, CATEGORY, LIMIT, DONATION_PAGE_URL

s = create_session()
r = s.get(DONATION_PAGE_URL, timeout=30)
print("status", r.status_code)
for pat in ["donationType", "ajax_check_month", "ajax_get_funds", "category"]:
    print(pat, r.text.count(pat))

for m in re.finditer(r"donationType.{0,120}", r.text):
    print("ctx:", m.group()[:120])

warm_up_session(s)
for payload in [
    {"year": "2024"},
    {"year": "2024", "donationType": "1"},
    {"year": "2024", "donationType": "2"},
    {"year": "2024", "category": "1"},
    {"year": "2024", "donationType": "1", "category": "1"},
]:
    data = post_form(s, CHECK_MONTH_URL, {k: str(v) for k, v in payload.items()})
    print("check_month", payload, "->", json.dumps(data, ensure_ascii=False)[:200])
