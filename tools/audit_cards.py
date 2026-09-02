import json
from pathlib import Path
from urllib.request import Request, urlopen

API_URL = "https://api.netdeck.gg/api/cards/cyberpunk"
PAGE_SIZE = 60

ROOT = Path(__file__).resolve().parent.parent
EXISTING_FILE = ROOT / "Cyberpunk-TCG-Cards.json"

AUDIT_FILE = ROOT / "tools" / "official_cards_audit.json"
COMPARISON_FILE = ROOT / "tools" / "cards_comparison.json"
MIGRATION_FILE = ROOT / "tools" / "cards_migration_report.json"


def fetch_cards(offset):
    url = f"{API_URL}?limit={PAGE_SIZE}&offset={offset}"
    print(f"Fetching: {url}")

    request = Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def get_all_cards():
    first = fetch_cards(0)

    total = first["total"]
    cards = list(first["items"])

    for offset in range(PAGE_SIZE, total, PAGE_SIZE):
        page = fetch_cards(offset)
        cards.extend(page["items"])

    unique = {}

    for card in cards:
        unique[card["id"]] = card

    return list(unique.values())


def is_retail(card):
    card_set = card.get("set") or {}
    return card_set.get("code") == "welcometonightcityretail"


def clean(card):
    card_set = card.get("set") or {}

    return {
        "id": card.get("id"),
        "external_id": card.get("external_id"),
        "name": card.get("name"),
        "display_name": card.get("display_name"),
        "slug": card.get("slug"),
        "type": card.get("card_type"),
        "cost": card.get("cost"),
        "power": card.get("power"),
        "ram": card.get("ram"),
        "color": card.get("color"),
        "rarity": card.get("rarity"),
        "set_code": card_set.get("code"),
        "set_name": card_set.get("name"),
        "print_number": card.get("print_number"),
        "rules_text": card.get("rules_text"),
        "flavor_text": card.get("flavor_text"),
        "artist": card.get("artist"),
        "source_image_url": card.get("source_image_url"),
        "image_url": card.get("image_url"),
        "is_eddiable": card.get("is_eddiable"),
        "legality": card.get("legality"),
    }


def load_existing():
    with EXISTING_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalise_name(name):
    if not name:
        return ""

    return (
        name.lower()
        .replace("—", "-")
        .replace("–", "-")
        .replace("’", "'")
        .strip()
    )


def extract_print_number(arena_id, card):
    """
    Try to recover the collector number from the old Arena ID.

    Existing Retail IDs look like:
        ms01-wnca-131
        ms01-wnca-132-a
        ms01-wnca-016

    Alpha IDs such as a001 do not have a Retail collector number.
    """

    if arena_id.startswith("ms01-wnca-"):
        value = arena_id[len("ms01-wnca-"):]

        # Special suffix such as 132-a.
        return value

    return None


def main():
    print("=" * 70)
    print("CYBERPUNK TCG - MIGRATION AUDIT")
    print("=" * 70)

    # ---------------------------------------------------------------
    # Download official data
    # ---------------------------------------------------------------

    all_cards = get_all_cards()

    retail = [
        clean(card)
        for card in all_cards
        if is_retail(card)
    ]

    retail.sort(
        key=lambda c: (
            c["print_number"] is None,
            c["print_number"] or ""
        )
    )

    print()
    print(f"Total API cards:      {len(all_cards)}")
    print(f"Official Retail:      {len(retail)}")

    # ---------------------------------------------------------------
    # Load existing Arena cards
    # ---------------------------------------------------------------

    existing = load_existing()

    print(f"Existing Arena cards: {len(existing)}")

    # ---------------------------------------------------------------
    # Build lookup tables
    # ---------------------------------------------------------------

    official_by_number = {}

    for card in retail:
        number = card.get("print_number")

        if number:
            official_by_number[number] = card

    official_by_name = {}

    for card in retail:
        name = normalise_name(card.get("name"))
        official_by_name.setdefault(name, []).append(card)

    # ---------------------------------------------------------------
    # Match existing cards
    # ---------------------------------------------------------------

    matched = []
    uncertain = []
    unmatched = []

    used_official_ids = set()

    for arena_id, arena_card in existing.items():

        arena_name = arena_card.get("name", "")
        print_number = extract_print_number(arena_id, arena_card)

        name_key = normalise_name(arena_name)

        candidates = []

        # Strongest match: collector number.
        if print_number:
            candidate = official_by_number.get(print_number)

            if candidate:
                candidates.append(candidate)

        # Secondary match: exact name.
        name_candidates = official_by_name.get(name_key, [])

        for candidate in name_candidates:
            if candidate not in candidates:
                candidates.append(candidate)

        if len(candidates) == 1:

            official = candidates[0]

            if official["id"] not in used_official_ids:
                matched.append({
                    "arena_id": arena_id,
                    "arena_card": arena_card,
                    "official": official,
                    "match_method": (
                        "print_number"
                        if print_number
                        and official.get("print_number") == print_number
                        else "name"
                    ),
                })

                used_official_ids.add(official["id"])
            else:
                uncertain.append({
                    "arena_id": arena_id,
                    "arena_card": arena_card,
                    "reason": "Official card already matched by another Arena entry",
                    "candidates": candidates,
                })

        elif len(candidates) > 1:

            uncertain.append({
                "arena_id": arena_id,
                "arena_card": arena_card,
                "reason": "Multiple possible official matches",
                "candidates": candidates,
            })

        else:

            unmatched.append({
                "arena_id": arena_id,
                "arena_card": arena_card,
                "reason": "No Retail match found",
            })

    # ---------------------------------------------------------------
    # Determine genuinely new official cards
    # ---------------------------------------------------------------

    new_cards = [
        card
        for card in retail
        if card["id"] not in used_official_ids
    ]

    # ---------------------------------------------------------------
    # Save migration report
    # ---------------------------------------------------------------

    report = {
        "summary": {
            "total_api_cards": len(all_cards),
            "official_retail_cards": len(retail),
            "existing_arena_cards": len(existing),
            "matched": len(matched),
            "uncertain": len(uncertain),
            "unmatched": len(unmatched),
            "new_official_cards": len(new_cards),
        },
        "matched": matched,
        "uncertain": uncertain,
        "unmatched": unmatched,
        "new_official_cards": new_cards,
    }

    with MIGRATION_FILE.open("w", encoding="utf-8") as f:
        json.dump(
            report,
            f,
            indent=2,
            ensure_ascii=False
        )

    # ---------------------------------------------------------------
    # Also preserve the official audit
    # ---------------------------------------------------------------

    with AUDIT_FILE.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "source": API_URL,
                "total_api_cards": len(all_cards),
                "total_retail_cards": len(retail),
                "cards": retail,
            },
            f,
            indent=2,
            ensure_ascii=False
        )

    # ---------------------------------------------------------------
    # Console output
    # ---------------------------------------------------------------

    print()
    print("=" * 70)
    print("MIGRATION RESULTS")
    print("=" * 70)

    print(f"Existing Arena cards:       {len(existing)}")
    print(f"Official Retail cards:      {len(retail)}")
    print(f"Confirmed matches:          {len(matched)}")
    print(f"Uncertain matches:           {len(uncertain)}")
    print(f"Unmatched old cards:         {len(unmatched)}")
    print(f"New official cards:          {len(new_cards)}")

    print()
    print("=" * 70)
    print("CONFIRMED MATCHES")
    print("=" * 70)

    for item in matched:
        official = item["official"]

        print(
            f"  {item['arena_id']:<22} -> "
            f"#{official['print_number']:<4} "
            f"{official['name']} "
            f"[{item['match_method']}]"
        )

    print()
    print("=" * 70)
    print("UNCERTAIN")
    print("=" * 70)

    if uncertain:
        for item in uncertain:
            print(
                f"  {item['arena_id']}: "
                f"{item['reason']}"
            )
    else:
        print("  None")

    print()
    print("=" * 70)
    print("UNMATCHED EXISTING CARDS")
    print("=" * 70)

    if unmatched:
        for item in unmatched:
            print(
                f"  {item['arena_id']}: "
                f"{item['arena_card'].get('name', '')}"
            )
    else:
        print("  None")

    print()
    print("=" * 70)
    print("NEW OFFICIAL RETAIL CARDS")
    print("=" * 70)

    for card in new_cards:
        print(
            f"  #{card['print_number']:<4} "
            f"{card['name']}"
        )

    print()
    print("Migration report:")
    print(MIGRATION_FILE)


if __name__ == "__main__":
    main()