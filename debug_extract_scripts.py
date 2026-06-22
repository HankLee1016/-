from __future__ import annotations

import re
import urllib.parse

import requests


def main() -> None:
    url = "https://donate.ccf.org.tw/19/donation-funds/"
    html = requests.get(url, timeout=30).text
    srcs = re.findall(r'<script[^>]+src="([^"]+)"', html)
    print("scripts", len(srcs))
    for s in srcs[:80]:
        print(urllib.parse.urljoin(url, s))


if __name__ == "__main__":
    main()

