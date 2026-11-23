"""HTTP-клиент проверок на stdlib urllib; конфигурация из окружения / .env."""

import os
import urllib.error
import urllib.request


def load_env_file(path):
    """Минимальный парсер .env: KEY=VALUE, строки без '=' и комментарии игнорируются."""
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def env(name, default=None, env_file=".env"):
    cached = getattr(env, "_file_cache", None)
    if cached is None:
        cached = load_env_file(env_file)
        env._file_cache = cached
    return os.environ.get(name) or cached.get(name) or default


class HttpResponse:
    def __init__(self, status, headers, body):
        self.status = status
        # HTTP-заголовки нечувствительны к регистру; сервер отдаёт их lowercase.
        self.headers = {k.lower(): v for k, v in headers.items()}
        self.body = body

    def header(self, name):
        return self.headers.get(name.lower())


class HttpClient:
    def __init__(self, base_url, timeout=10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get(self, path, api_key=None):
        request = urllib.request.Request(self.base_url + path, method="GET")
        if api_key:
            request.add_header("X-API-Key", api_key)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return HttpResponse(
                    response.status,
                    dict(response.headers.items()),
                    response.read().decode("utf-8", "replace"),
                )
        except urllib.error.HTTPError as e:
            return HttpResponse(e.code, dict(e.headers.items()), e.read().decode("utf-8", "replace"))
