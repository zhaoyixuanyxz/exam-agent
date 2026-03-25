import httpx
import trafilatura


def parse_url(url: str) -> str:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            r = client.get(url)
            r.raise_for_status()
            downloaded = r.text
    text = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
    if not text:
        return downloaded[:500_000] if downloaded else ""
    return text.strip()
