"""Apprise notification wrapper."""

from __future__ import annotations

try:
    from apprise import Apprise
except ImportError:
    Apprise = None


class Notifier:
    def __init__(self, notification_urls: list[str]):
        self.apobj = None
        if Apprise is None:
            print("[WARN] apprise is not installed. Notifications are disabled.")
            return

        self.apobj = Apprise()
        for url in notification_urls:
            self.apobj.add(url)

    def send(self, title: str, body: str) -> None:
        if self.apobj:
            self.apobj.notify(body=body, title=title)

    def test(self) -> None:
        self.send("RC Price Tracker Test", "Notifications are working correctly!")
