"""App 版本清单接口：未配置 404、合法清单八字段与类型、非法配置 500、未登录 401。

TestClient 走真实登录门控 + 路由 + pydantic 序列化；`core.config.APP_UPDATE` 逐用例注入，
不触碰真实 config.yaml / server_data（conftest 已把进程配置指向临时目录）。
"""

import unittest
from unittest import mock

from fastapi.testclient import TestClient

from core import config
from core.auth import make_login_key
from webapp.app import app

SHA256 = "0123456789abcdef" * 4
MANIFEST = {
    "version": "0.19.0",
    "version_code": 37,
    "apk_url": "https://oss.example.com/botero/app-release.apk",
    "sha256": SHA256,
    "size": 58976234,
    "notes": "修复若干问题\n新增深色模式",
    "min_supported_version_code": 30,
    "published_at": "2026-11-20 18:00:00",
}
AUTH = {"Authorization": "Bearer " + make_login_key(12345601)}


class AppVersionTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def _get(self, cfg, headers=AUTH):
        with mock.patch.object(config, "APP_UPDATE", cfg):
            return self.client.get("/api/app/version", headers=headers)

    def test_unconfigured_section_returns_404(self):
        r = self._get({})
        self.assertEqual(r.status_code, 404, r.text)
        self.assertEqual(r.json()["detail"], "未配置应用更新")

    def test_unconfigured_empty_apk_url_returns_404_not_empty_200(self):
        r = self._get(dict(MANIFEST, apk_url=""))
        self.assertEqual(r.status_code, 404, r.text)
        self.assertNotIn("version", r.json())

    def test_valid_manifest_returns_all_fields(self):
        r = self._get(MANIFEST)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body, MANIFEST)
        for key in ("version_code", "size", "min_supported_version_code"):
            self.assertIsInstance(body[key], int, key)
        for key in ("version", "apk_url", "sha256", "notes", "published_at"):
            self.assertIsInstance(body[key], str, key)

    def test_valid_manifest_normalizes_sha256_lowercase(self):
        r = self._get(dict(MANIFEST, sha256="AB" * 32))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["sha256"], "ab" * 32)

    def test_invalid_apk_url_scheme(self):
        r = self._get(dict(MANIFEST, apk_url="ftp://oss.example.com/app.apk"))
        self.assertEqual(r.status_code, 500, r.text)
        self.assertIn("apk_url", r.json()["detail"])

    def test_invalid_apk_url_not_absolute(self):
        r = self._get(dict(MANIFEST, apk_url="app-release.apk"))
        self.assertEqual(r.status_code, 500, r.text)
        self.assertIn("apk_url", r.json()["detail"])

    def test_invalid_sha256_not_hex(self):
        r = self._get(dict(MANIFEST, sha256="not-a-sha256"))
        self.assertEqual(r.status_code, 500, r.text)
        self.assertIn("sha256", r.json()["detail"])

    def test_invalid_size_negative(self):
        r = self._get(dict(MANIFEST, size=-1))
        self.assertEqual(r.status_code, 500, r.text)
        self.assertIn("size", r.json()["detail"])

    def test_invalid_size_not_integer(self):
        r = self._get(dict(MANIFEST, size="58976234.5"))
        self.assertEqual(r.status_code, 500, r.text)
        self.assertIn("size", r.json()["detail"])

    def test_invalid_version_code_not_positive(self):
        r = self._get(dict(MANIFEST, version_code=0))
        self.assertEqual(r.status_code, 500, r.text)
        self.assertIn("version_code", r.json()["detail"])

    def test_invalid_version_code_not_integer(self):
        r = self._get(dict(MANIFEST, version_code="abc"))
        self.assertEqual(r.status_code, 500, r.text)
        self.assertIn("version_code", r.json()["detail"])

    def test_invalid_empty_version(self):
        r = self._get(dict(MANIFEST, version=""))
        self.assertEqual(r.status_code, 500, r.text)
        self.assertIn("version", r.json()["detail"])

    def test_invalid_min_supported_version_code_negative(self):
        r = self._get(dict(MANIFEST, min_supported_version_code=-1))
        self.assertEqual(r.status_code, 500, r.text)
        self.assertIn("min_supported_version_code", r.json()["detail"])

    def test_invalid_non_mapping_section(self):
        r = self._get("oops")
        self.assertEqual(r.status_code, 500, r.text)
        self.assertIn("映射", r.json()["detail"])

    def test_unauthenticated_returns_401(self):
        r = self._get(MANIFEST, headers={})
        self.assertEqual(r.status_code, 401, r.text)
        self.assertNotIn("apk_url", r.json())


if __name__ == "__main__":
    unittest.main(verbosity=2)
