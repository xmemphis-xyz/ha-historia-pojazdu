"""Bounded retries, verification defaults and sanitized failure tests."""
import asyncio
import importlib.util
import pathlib
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('api_fetch', pathlib.Path(__file__).parents[1] / 'custom_components/historia_pojazdu/api.py')
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class Response:
    def __init__(self, report=None, status=200):
        self.cookies = {'XSRF-TOKEN': types.SimpleNamespace(value='secret')}
        self.report = report
        self.status = status
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    def raise_for_status(self):
        if self.status >= 400:
            raise api.aiohttp.ClientResponseError(None, (), status=self.status)
    async def json(self, **kwargs): return self.report


class Session:
    calls = []
    failures = 0
    api_status = 200
    def __init__(self, **kwargs): self.timeout = kwargs.get('timeout')
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.failures:
            type(self).failures -= 1
            raise asyncio.TimeoutError('sensitive details')
        if url == api._URL:
            return Response()
        return Response({'timelineData': {'insuranceExpiryDate': '2031-05-06', 'events': []}}, self.api_status)


class FetchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        Session.calls = []
        Session.failures = 0
        Session.api_status = 200
        self.sleeps = []
        async def fake_sleep(n): self.sleeps.append(n)
        self.patches = [patch.object(api.aiohttp, 'ClientSession', Session), patch.object(api.asyncio, 'sleep', fake_sleep)]
        for p in self.patches:
            p.start()

    async def asyncTearDown(self):
        for p in self.patches:
            p.stop()

    async def test_verified_tls_and_bound(self):
        result = await api.fetch_report('test', 'secret-vin', '2024-01-01')
        self.assertEqual(result[0].isoformat(), '2031-05-06')
        self.assertEqual(len(Session.calls), 2)
        for _, kwargs in Session.calls:
            self.assertNotIn('ssl', kwargs)  # aiohttp default verifies certificates
            self.assertEqual(kwargs['timeout'].total, 15)
            self.assertEqual(kwargs['timeout'].connect, 6)

    async def test_custom_session_factory_is_used_per_attempt(self):
        made = []
        def factory():
            made.append(Session())
            return made[-1]
        Session.failures = 1
        await api.fetch_report('test', 'vin', '2024-01-01', factory)
        self.assertEqual(len(made), 2)  # fresh session (fresh cookies) per attempt

    async def test_retries_sanitized_failure(self):
        Session.failures = 3
        with self.assertRaises(api.FetchError) as caught:
            await api.fetch_report('test', 'secret-vin', '2024-01-01')
        self.assertEqual(len(Session.calls), 3)
        self.assertEqual(self.sleeps, [1, 2])
        self.assertNotIn('secret', str(caught.exception))

    async def test_rejected_vehicle_is_not_retried(self):
        Session.api_status = 404
        with self.assertRaises(api.VehicleRejected) as caught:
            await api.fetch_report('test', 'secret-vin', '2024-01-01')
        self.assertEqual(len(Session.calls), 2)
        self.assertEqual(self.sleeps, [])
        self.assertIn('404', str(caught.exception))
        self.assertNotIn('secret', str(caught.exception))

    async def test_server_error_and_rate_limit_are_retried(self):
        for status in (503, 429):
            Session.calls = []
            self.sleeps.clear()
            Session.api_status = status
            with self.assertRaises(api.FetchError) as caught:
                await api.fetch_report('test', 'vin', '2024-01-01')
            self.assertNotIsInstance(caught.exception, api.VehicleRejected)
            self.assertEqual(self.sleeps, [1, 2])


if __name__ == '__main__': unittest.main()
