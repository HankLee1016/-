from __future__ import annotations

import re

import requests


def main() -> None:
    urls = [
        "https://donate.ccf.org.tw/config/fun/js/common.js",
        "https://donate.ccf.org.tw/config/fun/formsauth/front_formsauth.js",
        "https://donate.ccf.org.tw/config/fun/formsauth/check_tools.js?v=0425",
    ]
    needle = "ajax_get_funds_list.php"
    for url in urls:
        text = requests.get(url, timeout=30).text
        print("\n==", url, "len", len(text), "==")
        if needle in text:
            print("FOUND", needle)
            for m in re.finditer(r".{0,80}ajax_get_funds_list\\.php.{0,120}", text):
                print(m.group(0).replace("\n", "\\n"))
        else:
            print("not found")


if __name__ == "__main__":
    main()

