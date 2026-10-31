"""Use a consistent client identity for MiService login and device calls.

MiService 3.0.1's device User-Agent advertises MiHome 6.0.103, while
authentication advertises 11.3.203. On the local L05B the former receives
`-127 / client withdraw`; the login identity succeeds with the same token.
"""
from miservice import MiIOService as BaseMiIOService
from miservice.miaccount import UA_LOGIN


class MiIOService(BaseMiIOService):
    async def miio_request(self, uri: str, data):
        if not self.account:
            raise ValueError("MiIOService requires an account for API requests")

        def prepare_data(token, cookies):
            cookies["PassportDeviceId"] = token["deviceId"]
            return self.sign_data(uri, data, token["xiaomiio"][0])

        headers = {
            "User-Agent": UA_LOGIN,
            "x-xiaomi-protocal-flag-cli": "PROTOCAL-HTTP2",
        }
        response = await self.account.mi_request(
            "xiaomiio", self.server + uri, prepare_data, headers
        )
        if "result" not in response:
            raise RuntimeError(f"Error {uri}: {response}")
        return response["result"]
