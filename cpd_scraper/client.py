"""HTTP client: requests.Session + retry/backoff + timeout + หน่วงเวลาระหว่าง request"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config

log = logging.getLogger(__name__)


def use_os_trust_store() -> bool:
    """ให้ Python ใช้ใบรับรองของ Windows/macOS (แก้ SSL error หลัง proxy องค์กร)

    ต้องติดตั้งแพ็กเกจ `truststore` (Python 3.10+) ถ้าไม่มีจะข้ามไปเงียบ ๆ
    """
    try:
        import truststore  # type: ignore

        truststore.inject_into_ssl()
        log.debug("ใช้ OS trust store ผ่าน truststore แล้ว")
        return True
    except Exception:  # ImportError หรือ Python เวอร์ชันเก่า
        return False


class ApiError(RuntimeError):
    """เรียก API ไม่สำเร็จ หรือได้ response ที่ไม่ใช่ JSON"""


class CpdClient:
    def __init__(
        self,
        base_url: str = config.BASE_URL,
        timeout: float = 30.0,
        delay: float = 0.5,
        retries: int = 3,
        verify: Any = True,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url = base_url if base_url.endswith("/") else base_url + "/"
        self.timeout = timeout
        self.delay = delay
        self.verify = verify
        self._last_call = 0.0
        self.session = session or self._build_session(retries)

    @staticmethod
    def _build_session(retries: int) -> requests.Session:
        s = requests.Session()
        s.headers.update(config.DEFAULT_HEADERS)
        retry = Retry(
            total=retries,
            backoff_factor=1.0,  # 1s, 2s, 4s
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        return s

    def _throttle(self) -> None:
        wait = self.delay - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def post(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> tuple[List[Dict[str, Any]], str]:
        """POST แล้วคืน (rows, url จริงที่เรียก) โดย rows เป็น list ของ dict เสมอ"""
        url = self.base_url + path.lstrip("/")
        self._throttle()
        try:
            resp = self.session.post(
                url,
                params=params,
                json=body if body is not None else config.DEFAULT_BODY,
                timeout=self.timeout,
                verify=self.verify,
            )
        except requests.RequestException as exc:
            raise ApiError(f"เรียก {url} ไม่สำเร็จ: {exc}") from exc

        if resp.status_code >= 400:
            raise ApiError(f"HTTP {resp.status_code} จาก {resp.url}: {resp.text[:300]}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise ApiError(f"response จาก {resp.url} ไม่ใช่ JSON: {resp.text[:300]}") from exc

        return normalize_rows(data), resp.url


def normalize_rows(data: Any) -> List[Dict[str, Any]]:
    """API ส่ง array กลับมาเป็นหลัก แต่กันกรณีเป็น object เดี่ยวหรือห่อใน key อื่น"""
    if data is None:
        return []
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        for key in ("data", "result", "results", "items"):
            if isinstance(data.get(key), list):
                return [r for r in data[key] if isinstance(r, dict)]
        return [data]
    raise ApiError(f"รูปแบบ response ไม่รองรับ: {type(data).__name__}")
