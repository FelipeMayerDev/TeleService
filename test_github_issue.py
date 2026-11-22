#!/usr/bin/env python
"""Checagem do /issue: corpo da issue e erros legíveis, sem chamar o GitHub."""

import asyncio
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))

from providers.github import IssueError, create_issue, issue_body


class FakeResponse:
    def __init__(self, status, data=None):
        self.status, self.data = status, data

    async def json(self):
        return self.data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    def __init__(self, response):
        self.response, self.calls = response, []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def run(response):
    session = FakeSession(response)
    with mock.patch("providers.github.aiohttp.ClientSession", return_value=session):
        return asyncio.run(create_issue("tok", "dona/repo", "  Bug no PiP ", "corpo")), session


def test_issue():
    assert issue_body("  trava ao abrir  ", "Ana", "Discord (#geral)") == "trava ao abrir\n\n---\n_Aberta por **Ana** pelo Discord (#geral)._"
    assert issue_body(None, "Ana", "Telegram") == "_Aberta por **Ana** pelo Telegram._"

    url, session = run(FakeResponse(201, {"html_url": "https://github.com/dona/repo/issues/7"}))
    assert url == "https://github.com/dona/repo/issues/7"
    target, kwargs = session.calls[0]
    assert target == "https://api.github.com/repos/dona/repo/issues"
    assert kwargs["json"] == {"title": "Bug no PiP", "body": "corpo"}
    assert kwargs["headers"]["Authorization"] == "Bearer tok"

    for status, text in [(403, "permissão"), (410, "desativadas"), (500, "HTTP 500")]:
        try:
            run(FakeResponse(status))
        except IssueError as exc:
            assert text in str(exc), exc
        else:
            raise AssertionError(f"HTTP {status} deveria falhar")


if __name__ == "__main__":
    test_issue()
    print("ok")
