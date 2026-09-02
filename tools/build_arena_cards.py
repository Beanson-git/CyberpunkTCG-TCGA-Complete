import json
import re
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

EXISTING_FILE = ROOT / "Cyberpunk-TCG-Cards.json"
OFFICIAL_FILE = ROOT / "tools" / "official_cards_audit.json"

OUTPUT_FILE = ROOT / "Cyberpunk-TCG-Cards-generated.json"
REPORT_FILE = ROOT / "tools" / "cards_build_report.json"


RAM_COLORS = {
    "Red": "🟥 Red",
    "Blue": "🟦 Blue",
    "Green": "🟩 Green",
    "Yellow": "🟨 Yellow",
}


# ------------------------------------------------------------
# Known naming variations between the existing Arena database
# and the current official Retail database.
#
# Key = existing Arena name
# Value = official Retail name
# ------------------------------------------------------------

KNOWN_NAME_MATCHES = {
    "afterparty at lizzy's": "Afterparty at Lizzie's",
    "river wards - detective on the hunt":
        "River Ward — Detective on the Hunt",
}


def normalize_name(name):
    """
    Normalize names for reliable comparison.

    Handles:
    - em dash vs hyphen
    - en dash vs hyphen
    - apostrophe variants
    - accents
    - case
    - repeated whitespace
    """

    if not name:
        return ""

    name = str(name)

    # Dash normalization.
    name = name.replace("—", "-")
    name = name.replace("–", "-")

    # Apostrophe normalization.
    name = name.replace("’", "'")

    # Unicode normalization removes accents.
    name = unicodedata.normalize("NFKD", name)

    name = "".join(
        char
        for char in name
        if not unicodedata.combining(char)
    )

    name = name.lower()

    # Normalize whitespace.
    name = re.sub(r"\s+", " ", name).strip()

    return name


def clean_ram_color(color):
    """
    Convert official API colour into the Arena RAM Color format.
    """

    if not color:
        return None

    color = str(color).strip()

    return RAM_COLORS.get(color, color)


def make_arena_card(card, arena_id):
    """
    Convert an official Retail API card into the existing
    Arena-compatible schema.
    """

    card_name = card.get("name") or card.get("display_name") or ""
    card_type = card.get("type") or "Unit"
    card_cost = card.get("cost")

    # Preserve the official API value.
    # Some Legends intentionally have no printed cost,
    # represented by null in the official data.

    return {
        "id": arena_id,
        "isToken": False,
        "face": {
            "front": {
                "name": card_name,
                "type": card_type,
                "cost": card_cost,
                "image": card.get("source_image_url"),
                "isHorizontal": False
            }
        },
        "name": card_name,
        "type": card_type,
        "cost": card_cost,
        "RAM Color": clean_ram_color(card.get("color"))
    }


def main():

    print("Loading existing Arena cards...")

    with EXISTING_FILE.open("r", encoding="utf-8") as f:
        existing = json.load(f)

    print("Loading official Retail card audit...")

    with OFFICIAL_FILE.open("r", encoding="utf-8") as f:
        official_data = json.load(f)

    official_cards = official_data.get("cards", [])

    print(f"Existing Arena cards: {len(existing)}")
    print(f"Official Retail cards: {len(official_cards)}")

    # --------------------------------------------------------
    # Build official lookup tables
    # --------------------------------------------------------

    official_by_name = {}

    for card in official_cards:

        key = normalize_name(card.get("name"))

        if not key:
            continue

        official_by_name.setdefault(key, []).append(card)

    official_by_id = {
        card.get("id"): card
        for card in official_cards
        if card.get("id")
    }

    # --------------------------------------------------------
    # Output structures
    # --------------------------------------------------------

    output = {}

    matched = []
    preserved_legacy = []
    duplicate_existing = []
    ambiguous = []
    added = []

    # Tracks which official API cards have already been
    # represented in the generated Arena database.
    represented_official_ids = set()

    # --------------------------------------------------------
    # Process existing Arena cards
    # --------------------------------------------------------

    for arena_id, existing_card in existing.items():

        existing_name = existing_card.get("name", "")

        existing_key = normalize_name(existing_name)

        # ----------------------------------------------------
        # Check explicit known-name mappings first.
        # ----------------------------------------------------

        official_name_override = KNOWN_NAME_MATCHES.get(
            existing_key
        )

        if official_name_override:

            official_key = normalize_name(
                official_name_override
            )

            candidates = official_by_name.get(
                official_key,
                []
            )

        else:

            candidates = official_by_name.get(
                existing_key,
                []
            )

        # ----------------------------------------------------
        # No official match.
        # ----------------------------------------------------

        if not candidates:

            output[arena_id] = existing_card

            preserved_legacy.append({
                "arena_id": arena_id,
                "name": existing_name,
                "reason": "No current Retail match"
            })

            continue

        # ----------------------------------------------------
        # Multiple official candidates.
        # ----------------------------------------------------

        if len(candidates) > 1:

            output[arena_id] = existing_card

            ambiguous.append({
                "arena_id": arena_id,
                "existing_name": existing_name,
                "candidate_print_numbers": [
                    card.get("print_number")
                    for card in candidates
                ]
            })

            continue

        # ----------------------------------------------------
        # Exactly one official candidate.
        # ----------------------------------------------------

        official_card = candidates[0]

        official_id = official_card.get("id")

        # ----------------------------------------------------
        # The official card has already been represented by
        # another existing Arena entry.
        #
        # Example:
        # ms01-wnca-132-a
        # ms01-wnca-132
        #
        # Both are V — Streetkid.
        #
        # We preserve the second historical entry rather than
        # creating a second copy of the official Retail card.
        # ----------------------------------------------------

        if official_id in represented_official_ids:

            output[arena_id] = existing_card

            duplicate_existing.append({
                "arena_id": arena_id,
                "name": existing_name,
                "official_name": official_card.get("name"),
                "official_print_number":
                    official_card.get("print_number"),
                "official_id": official_id,
                "reason":
                    "Existing duplicate of an official Retail card"
            })

            preserved_legacy.append({
                "arena_id": arena_id,
                "name": existing_name,
                "reason":
                    "Duplicate existing entry; official Retail card already represented"
            })

            continue

        # ----------------------------------------------------
        # First representation of this official card.
        # ----------------------------------------------------

        output[arena_id] = make_arena_card(
            official_card,
            arena_id
        )

        represented_official_ids.add(official_id)

        matched.append({
            "arena_id": arena_id,
            "old_name": existing_name,
            "official_name": official_card.get("name"),
            "print_number": official_card.get("print_number"),
            "official_id": official_id,
            "match_type":
                "known-name" if official_name_override
                else "name"
        })

    # --------------------------------------------------------
    # Add official Retail cards which aren't represented yet.
    # --------------------------------------------------------

    for official_card in official_cards:

        official_id = official_card.get("id")

        if official_id in represented_official_ids:
            continue

        new_id = official_card.get("external_id")

        if not new_id:
            new_id = official_id

        # Make sure the new ID cannot overwrite an existing ID.
        if new_id in output:

            base_id = new_id
            counter = 2

            while f"{base_id}-{counter}" in output:
                counter += 1

            new_id = f"{base_id}-{counter}"

        output[new_id] = make_arena_card(
            official_card,
            new_id
        )

        represented_official_ids.add(official_id)

        added.append({
            "arena_id": new_id,
            "official_name": official_card.get("name"),
            "print_number": official_card.get("print_number"),
            "official_id": official_id
        })

    # --------------------------------------------------------
    # OFFICIAL COVERAGE VALIDATION
    # --------------------------------------------------------

    official_ids = {
        card.get("id")
        for card in official_cards
        if card.get("id")
    }

    missing_official_ids = sorted(
        official_ids - represented_official_ids
    )

    extra_official_ids = sorted(
        represented_official_ids - official_ids
    )

    # --------------------------------------------------------
    # Validate Arena structure.
    # --------------------------------------------------------

    validation_errors = []

    required_top_level = [
        "id",
        "isToken",
        "face",
        "name",
        "type",
        "cost",
        "RAM Color"
    ]

    required_front = [
        "name",
        "type",
        "cost",
        "image",
        "isHorizontal"
    ]

    for key, card in output.items():

        for field in required_top_level:

            if field not in card:

                validation_errors.append(
                    f"{key}: missing top-level field '{field}'"
                )

        try:

            front = card["face"]["front"]

            for field in required_front:

                if field not in front:

                    validation_errors.append(
                        f"{key}: missing face.front field '{field}'"
                    )

        except (KeyError, TypeError):

            validation_errors.append(
                f"{key}: invalid face.front structure"
            )

    # --------------------------------------------------------
    # Duplicate Arena IDs.
    # --------------------------------------------------------

    arena_ids = [
        card.get("id")
        for card in output.values()
    ]

    duplicate_ids = sorted({
        value
        for value in arena_ids
        if value is not None
        and arena_ids.count(value) > 1
    })

    if duplicate_ids:

        validation_errors.append(
            "Duplicate Arena IDs: "
            + ", ".join(duplicate_ids)
        )

    # --------------------------------------------------------
    # Duplicate card names.
    #
    # These are allowed for legacy cards, but reported.
    # --------------------------------------------------------

    name_map = {}

    for key, card in output.items():

        name = normalize_name(card.get("name"))

        if name:

            name_map.setdefault(
                name,
                []
            ).append(key)

    duplicate_names = {
        name: ids
        for name, ids in name_map.items()
        if len(ids) > 1
    }

    # --------------------------------------------------------
    # Write generated JSON.
    # --------------------------------------------------------

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )

        f.write("\n")

    # --------------------------------------------------------
    # Build report.
    # --------------------------------------------------------

    report = {

        "summary": {

            "existing_arena_cards":
                len(existing),

            "official_retail_cards":
                len(official_cards),

            "final_generated_cards":
                len(output),

            "matched_existing_cards":
                len(matched),

            "preserved_legacy_cards":
                len(preserved_legacy),

            "duplicate_existing_cards":
                len(duplicate_existing),

            "ambiguous_existing_cards":
                len(ambiguous),

            "new_official_cards_added":
                len(added),

            "official_cards_represented":
                len(represented_official_ids),

            "official_cards_expected":
                len(official_ids),

            "missing_official_cards":
                len(missing_official_ids),

            "extra_official_ids":
                len(extra_official_ids),

            "validation_errors":
                len(validation_errors),

            "duplicate_names":
                len(duplicate_names)
        },

        "matched":
            matched,

        "preserved_legacy":
            preserved_legacy,

        "duplicate_existing":
            duplicate_existing,

        "ambiguous":
            ambiguous,

        "added":
            added,

        "missing_official_cards":
            [
                {
                    "official_id": card.get("id"),
                    "name": card.get("name"),
                    "print_number":
                        card.get("print_number")
                }
                for card in official_cards
                if card.get("id") in missing_official_ids
            ],

        "duplicate_names":
            duplicate_names,

        "validation_errors":
            validation_errors
    }

    with REPORT_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            report,
            f,
            ensure_ascii=False,
            indent=2
        )

        f.write("\n")

    # --------------------------------------------------------
    # Console output.
    # --------------------------------------------------------

    print()
    print("=" * 65)
    print("ARENA CARD BUILD COMPLETE")
    print("=" * 65)

    print(
        f"Existing Arena cards:       {len(existing)}"
    )

    print(
        f"Official Retail cards:      {len(official_cards)}"
    )

    print(
        f"Matched existing cards:     {len(matched)}"
    )

    print(
        f"Preserved legacy cards:     {len(preserved_legacy)}"
    )

    print(
        f"Duplicate existing cards:   {len(duplicate_existing)}"
    )

    print(
        f"Ambiguous matches:          {len(ambiguous)}"
    )

    print(
        f"New official cards added:   {len(added)}"
    )

    print(
        f"Final generated cards:      {len(output)}"
    )

    print()

    print(
        f"Official cards represented: "
        f"{len(represented_official_ids)} / {len(official_ids)}"
    )

    print(
        f"Missing official cards:     "
        f"{len(missing_official_ids)}"
    )

    print(
        f"Validation errors:          "
        f"{len(validation_errors)}"
    )

    print(
        f"Duplicate names:            "
        f"{len(duplicate_names)}"
    )

    print()
    print("Generated file:")
    print(f"  {OUTPUT_FILE}")

    print()
    print("Build report:")
    print(f"  {REPORT_FILE}")

    print("=" * 65)

    if duplicate_existing:

        print()
        print("DUPLICATE EXISTING ENTRIES PRESERVED:")

        for item in duplicate_existing:

            print(
                f"  {item['arena_id']} - "
                f"{item['name']} "
                f"(official #{item['official_print_number']})"
            )

    if ambiguous:

        print()
        print("AMBIGUOUS MATCHES:")

        for item in ambiguous:

            print(
                f"  {item['arena_id']} - "
                f"{item['existing_name']}"
            )

    if missing_official_ids:

        print()
        print("MISSING OFFICIAL CARDS:")

        for card in official_cards:

            if card.get("id") in missing_official_ids:

                print(
                    f"  #{card.get('print_number')} "
                    f"{card.get('name')}"
                )

    if validation_errors:

        print()
        print("VALIDATION ERRORS:")

        for error in validation_errors:

            print(f"  {error}")


if __name__ == "__main__":
    main()