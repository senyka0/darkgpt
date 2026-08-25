import secrets
import string
import sys
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
QUESTIONS = [
    "What is 2 + 2?",
    "Name three programming languages.",
    "Write a short hello world in Python.",
]


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


def main() -> int:
    questions = sys.argv[1:] or QUESTIONS
    if len(questions) > 3:
        questions = questions[:3]

    client = DarkGPTClient()

    signup = client.register()
    print(f"[+] registered username={client.username} password={client.password} id={signup.get('id')}")

    csrf = client.fetch_csrf()
    print(f"[+] csrf={csrf}")

    client.login()
    session = client.get_session()
    print(f"[+] session={session}")
    print(f"[+] cookies={client.cookie_jar()}")

    status = client.trial_status()
    print(f"[+] trial status={status}")

    if not status.get("canTrial", False):
        print(f"[-] cannot use trial: {status.get('reason')} used={status.get('used')}/{status.get('max')}")
        return 1

    remaining = int(status.get("max", 3)) - int(status.get("used", 0))
    for i, q in enumerate(questions[:remaining], start=1):
        print(f"[*] question {i}/{remaining}: {q}")
        resp = client.ask_trial(q)
        print(f"[+] response {i}: {resp}")

    print(f"[+] final trial status={client.trial_status()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
