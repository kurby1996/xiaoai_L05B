import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from miservice.miaccount import UA_LOGIN
from xiaogpt.miio_compat import MiIOService


class ClientIdentityTests(unittest.IsolatedAsyncioTestCase):
    async def test_action_uses_login_identity_and_preserves_payload(self):
        account = SimpleNamespace(mi_request=AsyncMock(return_value={"result": {"code": 0}}))
        service = MiIOService(account)
        self.assertEqual(await service.miot_action("123", (5, 3), ["hello world"]), 0)
        sid, url, prepare, headers = account.mi_request.call_args.args
        self.assertEqual(sid, "xiaomiio")
        self.assertEqual(url, "https://api.io.mi.com/app/miotspec/action")
        self.assertEqual(headers["User-Agent"], UA_LOGIN)
        import json
        from base64 import b64encode
        cookies = {}
        request = prepare({"deviceId": "test", "xiaomiio": [b64encode(b"security").decode(), "token"]}, cookies)
        self.assertEqual(cookies, {"PassportDeviceId": "test"})
        self.assertEqual(json.loads(request["data"])["params"], {"did": "123", "siid": 5, "aiid": 3, "in": ["hello world"]})
