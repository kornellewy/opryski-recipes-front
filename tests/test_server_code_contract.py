"""Offline contract tests for the Anvil server gateway.

The frontend checkout does not include the MVP backend, so these tests replace
the Anvil HTTP/session modules with a deterministic fake and verify the
contract at the gateway boundary.
"""

import ast
import importlib
import sys
import types
import unittest
from pathlib import Path


class FakeHttpError(Exception):
    def __init__(self, status):
        self.status = status
        self.content = None


class FakeSession(dict):
    def set(self, key, value):
        self[key] = value


class ServerCodeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.calls = []
        cls.scripted = []
        cls.session = FakeSession()

        anvil = types.ModuleType("anvil")
        server = types.ModuleType("anvil.server")
        http = types.ModuleType("anvil.http")
        secrets = types.ModuleType("anvil.secrets")
        server.session = cls.session
        server.callable = lambda function: function
        http.HttpError = FakeHttpError
        http.request = cls._request
        secrets.get_secret = lambda name: "https://mvp.example"
        anvil.server = server
        anvil.http = http
        anvil.secrets = secrets
        sys.modules.update(
            {
                "anvil": anvil,
                "anvil.server": server,
                "anvil.http": http,
                "anvil.secrets": secrets,
            }
        )
        sys.path.insert(0, str(cls.root / "server_code"))
        cls.uplink = importlib.import_module("uplink_client")
        cls.api = importlib.import_module("api")
        cls.uplink.time.sleep = lambda _: None

    @classmethod
    def _request(cls, url, **kwargs):
        cls.calls.append((url, kwargs))
        if cls.scripted:
            result = cls.scripted.pop(0)
            if isinstance(result, BaseException):
                raise result
            return result
        if url.endswith("/auth/login"):
            return {"access_token": "jwt"}
        if url.endswith("/auth/me"):
            return {"id": "owner-1", "role": "owner"}
        return {"items": [], "total": 0}

    def setUp(self):
        self.calls.clear()
        self.scripted.clear()
        self.session.clear()

    def test_successful_login_uses_oauth2_fields(self):
        result = self.api.mvp_login("owner@example.com", "secret")
        self.assertTrue(result["ok"])
        self.assertEqual(self.session["mvp_jwt"], "jwt")
        login = self.calls[0][1]
        self.assertEqual(
            login["data"],
            {"username": "owner@example.com", "password": "secret", "grant_type": "password"},
        )
        self.assertNotIn("Idempotency-Key", login["headers"])

    def test_failed_me_rolls_back_session(self):
        self.scripted[:] = [{"access_token": "jwt-2"}, FakeHttpError(401)]
        result = self.api.mvp_login("owner@example.com", "secret")
        self.assertFalse(result["ok"])
        self.assertEqual(result["kind"], "session_validation")
        self.assertNotIn("mvp_jwt", self.session)

    def test_read_retries_http_5xx_and_transport_failures(self):
        self.session["mvp_jwt"] = "jwt"
        self.scripted[:] = [FakeHttpError(503), FakeHttpError(0), {"items": []}]
        result = self.uplink.MvpClient().request("GET", "/recipes")
        self.assertTrue(result["ok"])
        self.assertEqual(len(self.calls), 3)

    def test_mutations_are_not_retried_and_get_one_idempotency_key(self):
        self.scripted[:] = [FakeHttpError(503)]
        result = self.uplink.MvpClient().request("POST", "/recipes", payload={})
        self.assertFalse(result["ok"])
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(self.calls[0][1]["headers"].get("Idempotency-Key"))

    def test_invalid_export_format(self):
        self.session["mvp_jwt"] = "jwt"
        invalid = self.api.mvp_recipe_export("recipe-1", "csv")
        self.assertFalse(invalid["ok"])
        self.assertEqual(invalid["code"], 422)

    def test_exact_route_mapping(self):
        self.session["mvp_jwt"] = "jwt"
        self.scripted[:] = [{"items": []}, {"items": []}]
        self.api.mvp_recipe_export("recipe-1", "text")
        self.api.mvp_worker_my_tasks()
        self.assertIn("/recipes/recipe-1/export?format=text", self.calls[0][0])
        self.assertEqual(self.calls[1][0], "https://mvp.example/workers/me/tasks")

        self.calls.clear()
        self.scripted[:] = [{"ok": True}]
        self.api.mvp_task_action("task-1", "owner-authorize")
        self.assertEqual(self.calls[0][0], "https://mvp.example/spray-tasks/task-1/owner-authorize")

        self.calls.clear()
        self.scripted[:] = [{"computed": True}]
        self.api.mvp_recipe_compute("recipe-1", 2.5)
        self.assertEqual(self.calls[0][0], "https://mvp.example/recipes/recipe-1/compute?area_ha=2.5")

        self.calls.clear()
        self.scripted[:] = [{"items": []}]
        self.api.mvp_catalog(50, 0)
        self.assertIn("https://mvp.example/catalog/products?limit=50&offset=0", self.calls[0][0])

        self.calls.clear()
        self.scripted[:] = [{"items": []}]
        self.api.mvp_inventory_lots()
        self.assertEqual(self.calls[0][0], "https://mvp.example/inventory")

        self.calls.clear()
        self.scripted[:] = [{"received": True}]
        self.api.mvp_inventory_receipt({"quantity": 1})
        self.assertEqual(self.calls[0][0], "https://mvp.example/inventory/lots")

    def test_server_weather_snapshot_is_retryable_without_idempotency(self):
        self.session["mvp_jwt"] = "jwt"
        self.scripted[:] = [FakeHttpError(503), {"status": "green"}]
        result = self.api.mvp_server_weather_snapshot({"kwatera_ids": ["k1"]})
        self.assertTrue(result["ok"])
        self.assertEqual(len(self.calls), 2)
        self.assertNotIn("Idempotency-Key", self.calls[0][1]["headers"])

        self.calls.clear()
        self.scripted[:] = [{"status": "green"}, {"id": "task-1"}]
        result = self.api.mvp_create_task({"kwatera_ids": ["k1"]})
        self.assertTrue(result["ok"])
        self.assertEqual(self.calls[0][0], "https://mvp.example/weather/server-snapshot")
        self.assertNotIn("Idempotency-Key", self.calls[0][1]["headers"])
        self.assertEqual(self.calls[1][0], "https://mvp.example/spray-tasks")
        self.assertTrue(self.calls[1][1]["headers"].get("Idempotency-Key"))

    def test_thirty_callable_registrations_and_required_routes(self):
        source = (self.root / "server_code" / "api.py").read_text()
        tree = ast.parse(source)
        count = sum(
            isinstance(node, ast.FunctionDef)
            and any(isinstance(dec, ast.Attribute) and dec.attr == "callable" for dec in node.decorator_list)
            for node in ast.walk(tree)
        )
        self.assertEqual(count, 30)
        self.assertIn('"/workers/me/tasks"', source)
        self.assertIn('"/catalog/products"', source)
        self.assertIn('"/weather/server-snapshot"', source)


if __name__ == "__main__":
    unittest.main()
