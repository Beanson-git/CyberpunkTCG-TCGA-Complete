import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent

OFFICIAL_FILE = ROOT / "tools" / "official_cards_audit.json"
ARENA_FILE = ROOT / "Cyberpunk-TCG-Cards.json"
OUTPUT_FILE = ROOT / "tools" / "cards_comparison.json"


def normalize(name):
    """Normalize a card name for comparison."""
    if not name:
        return ""

    name = name.lower()

    # Normalize punctuation/dashes.
    name = name.replace("—", "-")
    name = name.replace("–", "-")

    # Collapse whitespace.
    name = re.sub(r"\s+", " ", name)

    return name.strip()


print("=" * 60)
print("CYBERPUNK TCG CARD COMPARISON")
print("=" * 60)

# ------------------------------------------------------------
# Load official cards
# ------------------------------------------------------------

print()
print("Loading official Retail cards...")

with open(OFFICIAL_FILE, "r", encoding="utf-8") as f:
    official_cards = json.load(f)

print(f"Official Retail cards: {len(official_cards)}")


# ------------------------------------------------------------
# Load TCG Arena cards
# ------------------------------------------------------------

print()
print("Loading TCG Arena cards...")

with open(ARENA_FILE, "r", encoding="utf-8") as f:
    arena_data = json.load(f)

print(f"Raw Arena entries: {len(arena_data)}")


# ------------------------------------------------------------
# Build Arena name lookup
# ------------------------------------------------------------

arena_by_name = {}

for key, card in arena_data.items():

    name = (
        card.get("name")
        or card.get("face", {})
             .get("front", {})
             .get("name")
    )

    if name:
        arena_by_name[normalize(name)] = {
            "id": key,
            "name": name,
            "data": card
        }


# ------------------------------------------------------------
# Compare
# ------------------------------------------------------------

already_in_arena = []
missing_from_arena = []
arena_not_in_official = []

official_names = set()


for card in official_cards:

    name = card.get("display_name") or card.get("name")

    normalized = normalize(name)

    official_names.add(normalized)

    if normalized in arena_by_name:

        already_in_arena.append({
            "print_number": card.get("print_number"),
            "name": name,
            "arena_id": arena_by_name[normalized]["id"]
        })

    else:

        missing_from_arena.append({
            "print_number": card.get("print_number"),
            "name": name,
            "card_type": card.get("card_type"),
            "color": card.get("color"),
            "cost": card.get("cost"),
            "power": card.get("power"),
            "ram": card.get("ram"),
            "printing_id": card.get("printing_id")
        })


# ------------------------------------------------------------
# Find Arena cards that aren't in the official Retail set
# ------------------------------------------------------------

for key, card in arena_data.items():

    name = (
        card.get("name")
        or card.get("face", {})
             .get("front", {})
             .get("name")
    )

    if not name:
        continue

    if normalize(name) not in official_names:

        arena_not_in_official.append({
            "arena_id": key,
            "name": name,
            "type": card.get("type")
        })


# ------------------------------------------------------------
# Print results
# ------------------------------------------------------------

print()
print("=" * 60)
print("RESULTS")
print("=" * 60)

print()
print(f"Official Retail cards:       {len(official_cards)}")
print(f"Already in Arena:             {len(already_in_arena)}")
print(f"Missing from Arena:           {len(missing_from_arena)}")
print(f"Arena cards not in Retail:    {len(arena_not_in_official)}")


print()
print("=" * 60)
print("MISSING FROM TCG ARENA")
print("=" * 60)

if missing_from_arena:

    for card in missing_from_arena:

        print(
            f"{card['print_number']:>4} | "
            f"{card['card_type']:<8} | "
            f"{card['name']}"
        )

else:

    print("None.")


print()
print("=" * 60)
print("ALREADY IN TCG ARENA")
print("=" * 60)

if already_in_arena:

    for card in already_in_arena:

        print(
            f"{card['print_number']:>4} | "
            f"{card['name']} | "
            f"Arena ID: {card['arena_id']}"
        )

else:

    print("None.")


print()
print("=" * 60)
print("ARENA CARDS NOT IN OFFICIAL RETAIL")
print("=" * 60)

if arena_not_in_official:

    for card in arena_not_in_official:

        print(
            f"{card['arena_id']} | "
            f"{card['name']}"
        )

else:

    print("None.")


# ------------------------------------------------------------
# Save comparison
# ------------------------------------------------------------

comparison = {
    "official_retail_count": len(official_cards),
    "already_in_arena": already_in_arena,
    "missing_from_arena": missing_from_arena,
    "arena_not_in_official_retail": arena_not_in_official
}

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:

    json.dump(
        comparison,
        f,
        indent=2,
        ensure_ascii=False
    )


print()
print("=" * 60)
print("COMPARISON WRITTEN")
print("=" * 60)

print(OUTPUT_FILE)