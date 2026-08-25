import json
import secrets
import string
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import requests

BASE = "https://private6vilgpt.site"
PROXY = (
    "http://f15fcfdf0b09453b9992c7c8e8142a12:"
    "b0d20c6d57df4349c71404e391be299e@resi.maskify.su:80"
)
PROXIES = {"http": PROXY, "https": PROXY}
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
)
STATE_PATH = Path(__file__).with_name("account.json")


def random_username(length: int = 12) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "u" + "".join(secrets.choice(alphabet) for _ in range(length))


def random_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*_-+="
    return "".join(secrets.choice(alphabet) for _ in range(length))


class DarkGPTClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.proxies.update(PROXIES)
        self.session.headers.update(
            {
                "User-Agent": UA,
                "Accept": "*/*",
                "Origin": BASE,
            }
        )
        self.username: str | None = None
        self.password: str | None = None
        self.user_id: str | None = None
        self.csrf_token: str | None = None

    def register(self, username: str | None = None, password: str | None = None) -> dict[str, Any]:
        self.username = username or random_username()
        self.password = password or random_password()
        self.session.get(f"{BASE}/signup", timeout=30)
        r = self.session.post(
            f"{BASE}/api/signup",
            json={"username": self.username, "password": self.password, "ref": None},
            headers={
                "Referer": f"{BASE}/signup",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        self.user_id = data.get("id")
        return data

    def fetch_csrf(self) -> str:
        r = self.session.get(
            f"{BASE}/api/auth/csrf",
            headers={
                "Referer": f"{BASE}/signup",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        r.raise_for_status()
        self.csrf_token = r.json()["csrfToken"]
        return self.csrf_token

    def login(self) -> dict[str, Any]:
        if not self.username or not self.password:
            raise RuntimeError("register first")
        if not self.csrf_token:
            self.fetch_csrf()
        r = self.session.post(
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
        r.raise_for_status()
        return r.json()

    def get_session(self) -> dict[str, Any]:
        r = self.session.get(
            f"{BASE}/api/auth/session",
            headers={
                "Referer": f"{BASE}/dashboard",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def trial_status(self) -> dict[str, Any]:
        r = self.session.get(
            f"{BASE}/api/chat/trial",
            headers={"Referer": f"{BASE}/dashboard"},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def ask_trial(self, message: str) -> dict[str, Any]:
        r = self.session.post(
            f"{BASE}/api/chat/trial",
            json={"message": message},
            headers={
                "Referer": f"{BASE}/dashboard",
                "Content-Type": "application/json",
            },
            timeout=180,
        )
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
        except requests.RequestException:
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
        except requests.RequestException as exc:
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


def extract_answer(response: dict[str, Any]) -> str:
    for key in ("content", "message", "reply", "text", "answer"):
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return json.dumps(response, ensure_ascii=False)


def ask_question(
    question: str,
    status_cb: Callable[[str], None] | None = None,
) -> str:
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
    return extract_answer(resp)


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

    print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
