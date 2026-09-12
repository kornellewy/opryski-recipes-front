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


class FakeSecretError(Exception):
    pass


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
        cls.secret_missing = False

        anvil = types.ModuleType("anvil")
        server = types.ModuleType("anvil.server")
        http = types.ModuleType("anvil.http")
        secrets = types.ModuleType("anvil.secrets")
        server.session = cls.session
        server.callable = lambda function: function
        http.HttpError = FakeHttpError
        http.request = cls._request
        secrets.SecretError = FakeSecretError
        secrets.get_secret = cls._get_secret
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
    def _get_secret(cls, name):
        if cls.secret_missing:
            raise FakeSecretError()
        return "https://mvp.example"

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
        type(self).secret_missing = False

    def test_missing_mvp_secret_is_an_explicit_configuration_result(self):
        type(self).secret_missing = True
        result = self.api.mvp_register("owner@example.com", "secret", "Owner")
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], 503)
        self.assertEqual(result["kind"], "configuration")
        self.assertEqual(len(self.calls), 0)

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
        result = self.api.mvp_server_weather_snapshot(50.1, 19.9)
        self.assertTrue(result["ok"])
        self.assertEqual(len(self.calls), 2)
        self.assertIn("/weather/server-snapshot?lat=50.1&lon=19.9", self.calls[0][0])
        self.assertNotIn("Idempotency-Key", self.calls[0][1]["headers"])

        self.calls.clear()
        self.scripted[:] = [{"status": "green"}, {"id": "task-1"}]
        result = self.api.mvp_create_task({"kwatera_ids": ["k1"], "weather_snapshot": {"status": "green"}})
        self.assertTrue(result["ok"])
        self.assertEqual(self.calls[0][0], "https://mvp.example/spray-tasks")
        self.assertTrue(self.calls[0][1]["headers"].get("Idempotency-Key"))

    def test_expected_http_errors_are_explicit_and_401_clears_session(self):
        self.session["mvp_jwt"] = "jwt"
        for status, kind in ((403, "forbidden"), (404, "not_found"), (409, "conflict")):
            self.scripted[:] = [FakeHttpError(status)]
            result = self.api.mvp_tasks()
            self.assertFalse(result["ok"])
            self.assertEqual(result["code"], status)
            self.assertEqual(result["kind"], kind)
        self.scripted[:] = [FakeHttpError(401)]
        result = self.api.mvp_tasks()
        self.assertFalse(result["ok"])
        self.assertNotIn("mvp_jwt", self.session)

    def test_all_thirty_callables_can_be_invoked(self):
        callables = {
            "mvp_login": ("owner@example.com", "secret"),
            "mvp_register": ("owner2@example.com", "secret", "Owner Two"),
            "mvp_logout": (),
            "mvp_session": (),
            "mvp_me": (),
            "mvp_dashboard": (),
            "mvp_weather": (50.1, 19.9),
            "mvp_kwatery": (),
            "mvp_create_kwatera": ({},),
            "mvp_tasks": (),
            "mvp_worker_my_tasks": (),
            "mvp_create_task": ({},),
            "mvp_task_action": ("task-1", "dispatch"),
            "mvp_task_audit": ("task-1",),
            "mvp_recipes": (),
            "mvp_create_recipe": ({},),
            "mvp_recipe_compute": ("recipe-1", 1),
            "mvp_recipe_validation": ("recipe-1",),
            "mvp_recipe_copy": ("recipe-1",),
            "mvp_recipe_export": ("recipe-1", "json"),
            "mvp_workers": (),
            "mvp_create_worker": ("worker@example.com", "secret", "Worker"),
            "mvp_catalog": (),
            "mvp_inventory": (),
            "mvp_inventory_lots": (),
            "mvp_inventory_movements": (),
            "mvp_inventory_reservation": ("reservation-1",),
            "mvp_inventory_receipt": ({},),
            "mvp_worker_me": (),
            "mvp_server_weather_snapshot": (50.1, 19.9),
        }
        self.assertEqual(len(callables), 30)
        for name, args in callables.items():
            self.session["mvp_jwt"] = "jwt"
            self.scripted[:] = []
            result = getattr(self.api, name)(*args)
            self.assertIsInstance(result, dict, name)

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
