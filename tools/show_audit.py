import json
from collections import Counter

with open("tools/official_cards_audit.json", encoding="utf-8") as f:
    cards = json.load(f)

print("Total:", len(cards))
print()

for card in cards:
    number = card["number"] or "???"
    card_type = card["type"] or "???"
    title = card["title"]

    print(f"{number:>3} | {card_type:<7} | {title}")

print()
print("=" * 50)
print("SUMMARY")
print("=" * 50)

print("By type:")
for card_type, count in Counter(c["type"] for c in cards).items():
    print(f"  {card_type}: {count}")

print()
print("With retail number:", sum(c["number"] is not None for c in cards))
print("Without retail number:", sum(c["number"] is None for c in cards))