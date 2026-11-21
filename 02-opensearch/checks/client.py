"""Небольшой HTTP-клиент для проверок стенда."""

import base64
import json
import ssl
from urllib.request import Request, urlopen


class Client:
    def __init__(self, base_url, username=None, password=None, ca_file=None):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.context = ssl.create_default_context(cafile=ca_file)

    def request(self, path, method="GET", data=None, content_type="application/json"):
        headers = {}
        if self.username is not None:
            token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            headers["Authorization"] = f"Basic {token}"
        if data is not None:
            headers["Content-Type"] = content_type
            if isinstance(data, dict):
                data = json.dumps(data).encode()
            elif isinstance(data, str):
                data = data.encode()
        request = Request(self.base_url + path, data=data, headers=headers, method=method)
        with urlopen(request, context=self.context, timeout=30) as response:
            return response.status, response.read().decode()

    def json(self, path, method="GET", data=None):
        _, body = self.request(path, method, data)
        return json.loads(body)
