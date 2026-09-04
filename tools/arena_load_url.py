"""
Generate the https://tcg-arena.fr/load/<b64> URL that registers a config
snapshot into your Arena account library.

TCG Arena's /load/ endpoint takes a base64-encoded, URL-encoded config URL:
    /load/<base64(url_encoded(config_url))>

Examples:
    # Pin to a specific commit SHA (reproducible; jsDelivr caches it forever):
    python tools/arena_load_url.py --sha 693ac88ab4c4d4972b0b468b0751c20cad9ccd8a

    # Track the branch head (Arena will pick up latest each new /load/ visit,
    # subject to jsDelivr's ~12h branch-alias cache — add --bust to defeat it):
    python tools/arena_load_url.py --branch cyberpunk-gameplay --bust

    # Point at the production (root) config instead of Test/:
    python tools/arena_load_url.py --sha 693ac88 --path Cyberpunk-TCG-Game.json

    # Fully custom URL passthrough:
    python tools/arena_load_url.py --url https://example.com/some-game.json
"""

import argparse
import base64
import subprocess
import time
from urllib.parse import quote

DEFAULT_REPO = "Beanson-git/CyberpunkTCG-TCGA-Complete"
DEFAULT_PATH = "Test/Cyberpunk-TCG-Game.json"
DEFAULT_BRANCH = "cyberpunk-gameplay"


def current_head_sha():
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def jsdelivr_url(repo, ref, path):
    return f"https://cdn.jsdelivr.net/gh/{repo}@{ref}/{path}"


def arena_load_url(config_url):
    encoded = quote(config_url, safe="")
    b64 = base64.b64encode(encoded.encode("ascii")).decode("ascii")
    return f"https://tcg-arena.fr/load/{b64}"


def main():
    parser = argparse.ArgumentParser(
        description="Generate a TCG Arena /load/ URL for a game config.",
    )
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--path", default=DEFAULT_PATH)
    ref_group = parser.add_mutually_exclusive_group()
    ref_group.add_argument("--sha", help="Pin to a specific commit SHA.")
    ref_group.add_argument("--branch", help="Track a branch head (e.g. cyberpunk-gameplay).")
    ref_group.add_argument("--head", action="store_true", help="Use current git HEAD SHA.")
    ref_group.add_argument("--url", help="Bypass jsDelivr and use this config URL verbatim.")
    parser.add_argument(
        "--bust",
        action="store_true",
        help="Append ?v=<unix timestamp> to bust jsDelivr / Arena fetch caches.",
    )
    args = parser.parse_args()

    if args.url:
        config_url = args.url
    else:
        if args.sha:
            ref = args.sha
        elif args.branch:
            ref = args.branch
        elif args.head:
            ref = current_head_sha()
        else:
            ref = DEFAULT_BRANCH
        config_url = jsdelivr_url(args.repo, ref, args.path)

    if args.bust:
        sep = "&" if "?" in config_url else "?"
        config_url = f"{config_url}{sep}v={int(time.time())}"

    print("Config URL:", config_url)
    print("Load URL:  ", arena_load_url(config_url))


if __name__ == "__main__":
    main()
