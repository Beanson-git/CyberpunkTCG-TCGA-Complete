import json
import re
import time
import unicodedata
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent.parent
CARD_FILE = ROOT / "Test" / "Cyberpunk-TCG-Cards.json"
IMAGE_DIR = ROOT / "Test" / "images"
REPORT_FILE = ROOT / "tools" / "choomdex_image_report.json"

BASE_URL = "https://choomdex.com/media/cards/"

IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def slugify(name):
    """Convert a card name into the CHOOMDEX image filename format."""

    # Unicode normalisation
    name = unicodedata.normalize("NFKD", name)

    # Common punctuation normalisation
    replacements = {
        "—": "-",
        "–": "-",
        "−": "-",
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "á": "a",
        "Á": "A",
        "é": "e",
        "É": "E",
        "í": "i",
        "Í": "I",
        "ó": "o",
        "Ó": "O",
        "ú": "u",
        "Ú": "U",
    }

    for old, new in replacements.items():
        name = name.replace(old, new)

    # Lowercase
    name = name.lower()

    # Apostrophes become hyphens in CHOOMDEX URLs
    name = name.replace("'", "-")

    # Anything that isn't a-z / 0-9 becomes a hyphen
    name = re.sub(r"[^a-z0-9]+", "-", name)

    # Collapse repeated hyphens
    name = re.sub(r"-+", "-", name)

    # Remove leading/trailing hyphens
    return name.strip("-")


def download(url, destination):
    """Download one image and verify that it is actually an image."""

    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Referer": "https://choomdex.com/",
        },
    )

    with urlopen(request, timeout=30) as response:
        content_type = response.headers.get("Content-Type", "")

        data = response.read()

        if not data:
            raise ValueError("Empty response")

        if "image/" not in content_type.lower():
            raise ValueError(
                f"Unexpected Content-Type: {content_type}"
            )

        destination.write_bytes(data)

        return len(data), content_type


def main():

    print()
    print("======================================")
    print(" CHOOMDEX CARD IMAGE DOWNLOADER")
    print("======================================")
    print()

    with CARD_FILE.open("r", encoding="utf-8") as f:
        cards = json.load(f)

    print(f"Cards in JSON: {len(cards)}")
    print(f"Image directory: {IMAGE_DIR}")
    print()

    results = []

    success = 0
    failed = 0
    skipped = 0

    for number, card in enumerate(cards.values(), start=1):

        card_id = card["id"]
        name = card["name"]

        slug = slugify(name)

        filename = f"{card_id}.webp"
        destination = IMAGE_DIR / filename
        url = BASE_URL + slug + ".webp"

        print(f"[{number}/{len(cards)}] {name}")
        print(f"    ID:   {card_id}")
        print(f"    URL:  {url}")

        # Don't download again if the file already exists
        if destination.exists() and destination.stat().st_size > 0:
            size = destination.stat().st_size

            print(f"    SKIP: already exists ({size:,} bytes)")
            skipped += 1

            results.append({
                "id": card_id,
                "name": name,
                "slug": slug,
                "url": url,
                "status": "skipped",
                "bytes": size,
            })

            print()
            continue

        try:

            size, content_type = download(url, destination)

            print(f"    OK:   {size:,} bytes")
            print(f"    Type: {content_type}")

            success += 1

            results.append({
                "id": card_id,
                "name": name,
                "slug": slug,
                "url": url,
                "status": "downloaded",
                "bytes": size,
                "content_type": content_type,
            })

        except (HTTPError, URLError, ValueError, TimeoutError, Exception) as e:

            if destination.exists():
                destination.unlink()

            print(f"    FAIL: {e}")

            failed += 1

            results.append({
                "id": card_id,
                "name": name,
                "slug": slug,
                "url": url,
                "status": "failed",
                "error": str(e),
            })

        print()

        # Small delay so we don't hammer the site
        time.sleep(0.15)

    report = {
        "card_count": len(cards),
        "downloaded": success,
        "skipped": skipped,
        "failed": failed,
        "results": results,
    }

    with REPORT_FILE.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print()
    print("======================================")
    print(" COMPLETE")
    print("======================================")
    print(f"Cards:       {len(cards)}")
    print(f"Downloaded:  {success}")
    print(f"Skipped:     {skipped}")
    print(f"Failed:      {failed}")
    print()
    print(f"Images:      {IMAGE_DIR}")
    print(f"Report:      {REPORT_FILE}")
    print()


if __name__ == "__main__":
    main()