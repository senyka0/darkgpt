import base64
import io
import json
import random
import secrets
import string
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

BASE = "https://private6vilgpt.site"
PROXY_PATH = Path(__file__).with_name("proxy.txt")
_USER_AGENTS: list[str] = [
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    # Firefox on Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:136.0) Gecko/20100101 Firefox/136.0",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0",
    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:137.0) Gecko/20100101 Firefox/137.0",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    # Chrome on Android
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36",
]

STATE_PATH = Path(__file__).with_name("account.json")
MAX_RETRIES = 3


def random_user_agent() -> str:
    return random.choice(_USER_AGENTS)


def load_proxies() -> list[str]:
    if not PROXY_PATH.exists():
        raise RuntimeError(f"proxy file not found: {PROXY_PATH}")

    proxies: list[str] = []
    for line in PROXY_PATH.read_text().splitlines():
        proxy = line.strip()
        if not proxy:
            continue
        if "://" not in proxy:
            proxy = f"http://{proxy}"
        if proxy not in proxies:
            proxies.append(proxy)

    if not proxies:
        raise RuntimeError(f"no proxies found in {PROXY_PATH}")
    return proxies


_PROXIES: list[str] = load_proxies()


def random_proxy() -> str:
    return random.choice(_PROXIES)


def random_username(length: int = 12) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "u" + "".join(secrets.choice(alphabet) for _ in range(length))


def random_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*_-+="
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _proxies_dict(proxy_url: str) -> dict[str, str]:
    return {"http": proxy_url, "https": proxy_url}


class DarkGPTClient:
    def __init__(self) -> None:
        self._proxy = random_proxy()
        self._ua = random_user_agent()
        self.session = requests.Session()
        self.session.proxies.update(_proxies_dict(self._proxy))
        self.session.headers.update(
            {
                "User-Agent": self._ua,
                "Accept": "*/*",
                "Origin": BASE,
            }
        )
        self.username: str | None = None
        self.password: str | None = None
        self.user_id: str | None = None
        self.csrf_token: str | None = None

    def _rotate_proxy(self) -> None:
        new_proxy = random_proxy()
        while new_proxy == self._proxy and len(_PROXIES) > 1:
            new_proxy = random_proxy()
        self._proxy = new_proxy
        self.session.proxies.update(_proxies_dict(self._proxy))
        print(f"[*] rotated proxy to {self._proxy}")

    def _rotate_user_agent(self) -> None:
        new_ua = random_user_agent()
        while new_ua == self._ua and len(_USER_AGENTS) > 1:
            new_ua = random_user_agent()
        self._ua = new_ua
        self.session.headers.update({"User-Agent": self._ua})
        print(f"[*] rotated UA to {self._ua[:60]}...")

    def _request_retry(self, fn: Callable[[], requests.Response]) -> requests.Response:
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return fn()
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < MAX_RETRIES:
                    print(f"[-] attempt {attempt}/{MAX_RETRIES} failed: {exc}")
                    self._rotate_proxy()
                    self._rotate_user_agent()
        raise RuntimeError(
            f"all {MAX_RETRIES} proxy attempts failed"
        ) from last_exc

    def register(
        self, username: str | None = None, password: str | None = None
    ) -> dict[str, Any]:
        self.username = username or random_username()
        self.password = password or random_password()

        def get_signup() -> requests.Response:
            return self.session.get(f"{BASE}/signup", timeout=30)

        self._request_retry(get_signup)

        def post_signup() -> requests.Response:
            return self.session.post(
                f"{BASE}/api/signup",
                json={"username": self.username, "password": self.password, "ref": None},
                headers={
                    "Referer": f"{BASE}/signup",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )

        r = self._request_retry(post_signup)
        r.raise_for_status()
        data = r.json()
        self.user_id = data.get("id")
        return data

    def fetch_csrf(self) -> str:
        def do() -> requests.Response:
            return self.session.get(
                f"{BASE}/api/auth/csrf",
                headers={
                    "Referer": f"{BASE}/signup",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )

        r = self._request_retry(do)
        r.raise_for_status()
        self.csrf_token = r.json()["csrfToken"]
        return self.csrf_token

    def login(self) -> dict[str, Any]:
        if not self.username or not self.password:
            raise RuntimeError("register first")
        if not self.csrf_token:
            self.fetch_csrf()

        def do() -> requests.Response:
            return self.session.post(
                f"{BASE}/api/auth/callback/credentials",
                data={
                    "username": self.username,
                    "password": self.password,
                    "redirect": "false",
                    "csrfToken": self.csrf_token,
                    "callbackUrl": f"{BASE}/signup",
                    "json": "true",
                },
                headers={
                    "Referer": f"{BASE}/signup",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=30,
            )

        r = self._request_retry(do)
        r.raise_for_status()
        return r.json()

    def get_session(self) -> dict[str, Any]:
        def do() -> requests.Response:
            return self.session.get(
                f"{BASE}/api/auth/session",
                headers={
                    "Referer": f"{BASE}/dashboard",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )

        r = self._request_retry(do)
        r.raise_for_status()
        return r.json()

    def trial_status(self) -> dict[str, Any]:
        def do() -> requests.Response:
            return self.session.get(
                f"{BASE}/api/chat/trial",
                headers={"Referer": f"{BASE}/dashboard"},
                timeout=30,
            )

        r = self._request_retry(do)
        r.raise_for_status()
        return r.json()

    def ask_trial(self, message: str) -> dict[str, Any]:
        def do() -> requests.Response:
            return self.session.post(
                f"{BASE}/api/chat/trial",
                json={"message": message},
                headers={
                    "Referer": f"{BASE}/dashboard",
                    "Content-Type": "application/json",
                },
                timeout=180,
            )

        r = self._request_retry(do)
        r.raise_for_status()
        return r.json()

    def cookie_jar(self) -> dict[str, str]:
        return {c.name: c.value for c in self.session.cookies}

    def remaining_trials(self, status: dict[str, Any] | None = None) -> int:
        status = status or self.trial_status()
        if not status.get("canTrial", False):
            return 0
        return max(0, int(status.get("max", 3)) - int(status.get("used", 0)))

    def restore(self, state: dict[str, Any]) -> None:
        self.username = state.get("username")
        self.password = state.get("password")
        self.user_id = state.get("user_id")
        self.csrf_token = state.get("csrf_token")
        for name, value in state.get("cookies", {}).items():
            self.session.cookies.set(name, value, domain="private6vilgpt.site")

    def dump_state(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "password": self.password,
            "user_id": self.user_id,
            "csrf_token": self.csrf_token,
            "cookies": self.cookie_jar(),
        }

    def ensure_logged_in(self) -> None:
        try:
            session = self.get_session()
            if session.get("user"):
                return
        except (requests.RequestException, RuntimeError):
            pass
        self.fetch_csrf()
        self.login()

    def setup_fresh_account(self) -> None:
        signup = self.register()
        print(
            f"[+] registered username={self.username} "
            f"password={self.password} id={signup.get('id')}"
        )
        self.fetch_csrf()
        self.login()
        session = self.get_session()
        print(f"[+] session={session}")


def load_state() -> dict[str, Any] | None:
    if not STATE_PATH.exists():
        return None
    try:
        return json.loads(STATE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_state(client: DarkGPTClient) -> None:
    STATE_PATH.write_text(json.dumps(client.dump_state(), indent=2))


def ensure_working_account(
    client: DarkGPTClient,
    status_cb: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    def notify(message: str) -> None:
        if status_cb:
            status_cb(message)

    state = load_state()
    if state and state.get("username") and state.get("password"):
        notify("Restoring saved account...")
        client.restore(state)
        try:
            client.ensure_logged_in()
            status = client.trial_status()
            remaining = client.remaining_trials(status)
            print(
                f"[+] restored account={client.username} "
                f"trial used={status.get('used')}/{status.get('max')} "
                f"remaining={remaining}"
            )
            if remaining > 0:
                save_state(client)
                return status
        except (requests.RequestException, RuntimeError) as exc:
            print(f"[-] saved account failed: {exc}")

    notify("Creating new account...")
    client.setup_fresh_account()
    status = client.trial_status()
    remaining = client.remaining_trials(status)
    print(
        f"[+] trial used={status.get('used')}/{status.get('max')} "
        f"remaining={remaining}"
    )
    save_state(client)
    return status


@dataclass
class AnswerResult:
    text: str = ""
    images: list[bytes] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.text and not self.images


def _is_image_url(url: str) -> bool:
    """Heuristic: check if a URL looks like it points to an image."""
    lowered = url.lower()
    image_exts = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg")
    image_hosts = ("imgur.com", "cdn.discordapp.com", "i.imgur.com", "files.catbox.moe")
    if lowered.endswith(image_exts):
        return True
    if any(h in lowered for h in image_hosts):
        return True
    return False


def _download_image(url: str, session: requests.Session) -> bytes | None:
    try:
        r = session.get(url, timeout=30)
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "")
        if "image" in content_type or url.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
            return r.content
    except requests.RequestException:
        pass
    return None


def extract_answer(response: dict[str, Any]) -> AnswerResult:
    result = AnswerResult()

    # First try known text keys
    for key in ("content", "message", "reply", "text", "answer"):
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            result.text = value.strip()
            break

    if not result.text and not isinstance(response.get("content"), str):
        result.text = json.dumps(response, ensure_ascii=False)

    # Look for image URLs anywhere in the response
    def _collect_urls(obj: Any, urls: list[str]) -> None:
        if isinstance(obj, str):
            if obj.startswith("http://") or obj.startswith("https://"):
                urls.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                _collect_urls(v, urls)
        elif isinstance(obj, list):
            for item in obj:
                _collect_urls(item, urls)

    all_urls: list[str] = []
    _collect_urls(response, all_urls)

    # Also check for dedicated image keys
    image_keys = ("images", "image", "imageUrl", "image_url", "file", "url", "data")
    for key in image_keys:
        value = response.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    if item.startswith("http"):
                        all_urls.append(item)
                    elif _is_image_url(item):
                        all_urls.append(item)
        elif isinstance(value, str):
            if value.startswith("http"):
                all_urls.append(value)
            elif _is_image_url(value):
                all_urls.append(value)

    # Deduplicate and filter for image URLs
    seen: set[str] = set()
    image_urls: list[str] = []
    for url in all_urls:
        url = url.strip()
        if url and url not in seen and _is_image_url(url):
            seen.add(url)
            image_urls.append(url)

    # Also check for base64-encoded images in the response
    def _collect_base64(obj: Any, images: list[bytes]) -> None:
        if isinstance(obj, str):
            for prefix in ("data:image/", "iVBOR", "/9j/", "R0lGOD"):
                if prefix in obj:
                    try:
                        if "base64," in obj:
                            b64 = obj.split("base64,", 1)[1].split('"')[0].split("'")[0]
                        else:
                            b64 = obj
                        b64 = b64.strip().rstrip(";")
                        if len(b64) > 100:
                            decoded = base64.b64decode(b64)
                            if len(decoded) > 100:
                                images.append(decoded)
                    except Exception:
                        pass
                    break
        elif isinstance(obj, dict):
            for v in obj.values():
                _collect_base64(v, images)
        elif isinstance(obj, list):
            for item in obj:
                _collect_base64(item, images)

    _collect_base64(response, result.images)

    return result


def _extract_image_urls(response: dict[str, Any]) -> list[str]:
    """Extract image URLs from a response dict (public helper)."""
    def _collect(obj: Any, urls: list[str]) -> None:
        if isinstance(obj, str):
            if (obj.startswith("http://") or obj.startswith("https://")) and _is_image_url(obj):
                urls.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                _collect(v, urls)
        elif isinstance(obj, list):
            for item in obj:
                _collect(item, urls)

    all_urls: list[str] = []
    _collect(response, all_urls)

    image_keys = ("images", "image", "imageUrl", "image_url", "file", "url", "data")
    for key in image_keys:
        value = response.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.startswith("http") and _is_image_url(item):
                    all_urls.append(item)
        elif isinstance(value, str) and value.startswith("http") and _is_image_url(value):
            all_urls.append(value)

    seen: set[str] = set()
    result: list[str] = []
    for url in all_urls:
        url = url.strip()
        if url and url not in seen:
            seen.add(url)
            result.append(url)
    return result


def ask_question(
    question: str,
    status_cb: Callable[[str], None] | None = None,
) -> AnswerResult:
    def notify(message: str) -> None:
        if status_cb:
            status_cb(message)

    client = DarkGPTClient()
    status = ensure_working_account(client, status_cb)

    if client.remaining_trials(status) <= 0:
        notify("No free questions left, creating new account...")
        client = DarkGPTClient()
        client.setup_fresh_account()
        status = client.trial_status()
        save_state(client)
        if client.remaining_trials(status) <= 0:
            raise RuntimeError(f"new account has no trials: {status}")

    notify("Sending question...")
    print(f"[*] asking: {question}")
    resp = client.ask_trial(question)
    print(f"[+] response: {resp}")

    final = client.trial_status()
    print(
        f"[+] final trial used={final.get('used')}/{final.get('max')} "
        f"remaining={client.remaining_trials(final)}"
    )
    save_state(client)

    result = extract_answer(resp)

    # Download any image URLs found in the response
    if result.text:
        notify("Downloading images...")
    for url in _extract_image_urls(resp):
        img_data = _download_image(url, client.session)
        if img_data:
            result.images.append(img_data)
            print(f"[+] downloaded image from {url} ({len(img_data)} bytes)")

    return result


def main() -> int:
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <question>")
        return 1

    question = " ".join(sys.argv[1:]).strip()
    if not question:
        print(f"usage: {sys.argv[0]} <question>")
        return 1

    try:
        answer = ask_question(question)
    except Exception as exc:
        print(f"[-] {exc}")
        return 1

    if answer.text:
        print(answer.text)
    if answer.images:
        print(f"[+] {len(answer.images)} image(s) returned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())