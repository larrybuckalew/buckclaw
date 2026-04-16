"""Simple web reading provider using httpx and regex tag stripping."""
from __future__ import annotations

import re

import httpx

from mybot.provider.web_read.base import ReadResult, WebReadProvider


class HttpxReadProvider(WebReadProvider):
    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout

    async def read(self, url: str) -> ReadResult:
        """Fetch and read a web page.
        
        Args:
            url: The URL to fetch.
            
        Returns:
            ReadResult with content and metadata, or error message.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/91.0.4472.124 Safari/537.36"
                        )
                    },
                )
                response.raise_for_status()
                html = response.text

                # Extract title from <title> tag
                title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
                title = title_match.group(1).strip() if title_match else ""

                # Remove script and style tags
                html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.IGNORECASE | re.DOTALL)
                html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.IGNORECASE | re.DOTALL)

                # Remove all HTML tags
                html = re.sub(r"<[^>]+>", "", html)

                # Collapse whitespace
                html = re.sub(r"\s+", " ", html).strip()

                # Truncate to 8000 chars
                content = html[:8000]

                return ReadResult(url=url, title=title, content=content)
        except Exception as e:
            return ReadResult(url=url, title="", content="", error=str(e))
