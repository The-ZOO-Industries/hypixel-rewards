"""Claim a Hypixel daily reward from the terminal.

No browser is opened — everything goes through plain HTTPS requests to
rewards.hypixel.net.

Usage:
    python claim.py
    python claim.py https://rewards.hypixel.net/claim-reward/<id>
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

import requests


BASE = "https://rewards.hypixel.net"
CLAIM_URL_RE = re.compile(r"/claim-reward/([A-Za-z0-9]+)")
SECURITY_TOKEN_RE = re.compile(r'window\.securityToken\s*=\s*"([^"]+)"')
APP_DATA_RE = re.compile(r"window\.appData\s*=\s*'(.*?)';", re.DOTALL)

# Cannot contain "rewardclaim" — that string is filtered server-side.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

RARITY_COLOURS = {
    "COMMON": "\033[37m",
    "UNCOMMON": "\033[32m",
    "RARE": "\033[34m",
    "EPIC": "\033[35m",
    "LEGENDARY": "\033[33m",
    "MYTHIC": "\033[31m",
    "SPECIAL": "\033[36m",
}
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


def parse_session_id(link: str) -> str:
    link = link.strip()
    m = CLAIM_URL_RE.search(link)
    if m:
        return m.group(1)
    # Allow bare session IDs too.
    if re.fullmatch(r"[A-Za-z0-9]+", link):
        return link
    raise ValueError(f"Could not extract a reward id from: {link!r}")


def fetch_reward_page(session: requests.Session, session_id: str) -> dict[str, Any]:
    url = f"{BASE}/claim-reward/{session_id}"
    r = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
    r.raise_for_status()
    html = r.text

    token_match = SECURITY_TOKEN_RE.search(html)
    if not token_match:
        raise RuntimeError("Could not find window.securityToken — page layout changed?")
    security_token = token_match.group(1)

    data_match = APP_DATA_RE.search(html)
    if not data_match:
        raise RuntimeError("Could not find window.appData — page layout changed?")
    app_data = json.loads(data_match.group(1))

    return {
        "security_token": security_token,
        "app_data": app_data,
    }


def format_reward(reward: dict[str, Any]) -> str:
    rarity = reward.get("rarity", "COMMON").upper()
    colour = RARITY_COLOURS.get(rarity, "")
    kind = reward.get("reward", "?")
    parts: list[str] = []
    if "amount" in reward:
        parts.append(f"{reward['amount']:,}")
    parts.append(kind)
    if reward.get("gameType"):
        parts.append(f"({reward['gameType']})")
    if reward.get("package"):
        parts.append(f"[{reward['package']}]")
    if reward.get("key"):
        parts.append(f"key={reward['key']}")
    label = " ".join(parts)
    return f"{colour}{BOLD}{rarity}{RESET}{colour} - {label}{RESET}"


def print_rewards(app_data: dict[str, Any]) -> None:
    rewards = app_data.get("rewards", [])
    streak = app_data.get("dailyStreak", {})
    print()
    print(f"{BOLD}Session:{RESET} {app_data.get('id')}")
    if streak:
        print(
            f"{BOLD}Daily streak:{RESET} day {streak.get('value')} "
            f"(score {streak.get('score')}, best {streak.get('highScore')})"
        )
    print(f"{BOLD}Skippable ad:{RESET} {app_data.get('skippable')}")
    print()
    print(f"{BOLD}Pick a reward:{RESET}")
    for i, rw in enumerate(rewards, start=1):
        print(f"  {BOLD}{i}{RESET}. {format_reward(rw)}")
    print()


JUNK_LEGENDARY = {"dust"}
PREFERRED_COIN_GAMES = {
    "UHC": "UHC Champions",
    "SURVIVAL_GAMES": "Blitz SG",
    "WALLS3": "Mega Walls",
}
RARITY_ORDER = {"COMMON": 0, "RARE": 1, "EPIC": 2, "LEGENDARY": 3}


def _reward(r: dict[str, Any]) -> str:
    return (r.get("reward") or "").lower()


def _rarity(r: dict[str, Any]) -> str:
    return (r.get("rarity") or "").upper()


def auto_select(rewards: list[dict[str, Any]]) -> tuple[int | None, str]:
    """Pick a reward automatically. Returns (index_or_None, reason).

    Order of preference:
      1. Souls — unless blocked by a real (non-dust) LEGENDARY, or by a
         "tokens" reward with amount > 1.
      2. Coins from UHC Champions, Blitz SG, or Mega Walls.
      3. Highest rarity on offer.
    """
    legendary_block = next(
        (
            r
            for r in rewards
            if _rarity(r) == "LEGENDARY" and _reward(r) not in JUNK_LEGENDARY
        ),
        None,
    )
    big_tokens = next(
        (r for r in rewards if _reward(r) == "tokens" and int(r.get("amount", 0)) > 1),
        None,
    )
    souls_idx = next(
        (i for i, r in enumerate(rewards) if _reward(r) == "souls"),
        None,
    )

    if souls_idx is not None and legendary_block is None and big_tokens is None:
        return souls_idx, f"souls ({rewards[souls_idx].get('amount')})"

    for i, r in enumerate(rewards):
        if _reward(r) == "coins" and r.get("gameType") in PREFERRED_COIN_GAMES:
            return i, f"{PREFERRED_COIN_GAMES[r['gameType']]} coins ({r.get('amount'):,})"

    best_idx, best_rank = None, -1
    for i, r in enumerate(rewards):
        rank = RARITY_ORDER.get(_rarity(r), -1)
        if rank > best_rank:
            best_rank, best_idx = rank, i
    if best_idx is not None:
        return best_idx, f"best rarity ({_rarity(rewards[best_idx])})"

    return None, "no rule matched"


def prompt_choice(n: int) -> int:
    while True:
        try:
            raw = input(f"Choose 1-{n} (q to quit): ").strip().lower()
        except EOFError:
            raise SystemExit(1)
        if raw in {"q", "quit", "exit"}:
            print("Cancelled.")
            raise SystemExit(0)
        if raw.isdigit():
            v = int(raw)
            if 1 <= v <= n:
                return v - 1
        print(f"  {DIM}Please enter a number between 1 and {n}.{RESET}")


def claim_reward(
    session: requests.Session,
    session_id: str,
    option: int,
    active_ad: int,
    security_token: str,
) -> tuple[int, str]:
    r = session.post(
        f"{BASE}/claim-reward/claim",
        params={
            "id": session_id,
            "option": option,
            "activeAd": active_ad,
            "_csrf": security_token,
        },
        headers={
            "User-Agent": USER_AGENT,
            "Referer": f"{BASE}/claim-reward/{session_id}",
            "Origin": BASE,
        },
        timeout=15,
    )
    return r.status_code, r.text


def read_link_interactively() -> str:
    print(f"{BOLD}Hypixel reward claimer{RESET}")
    print(f"{DIM}Paste your reward link (or just the id) and press Enter.{RESET}")
    try:
        link = input("> ").strip()
    except EOFError:
        raise SystemExit(1)
    if not link:
        print("No link provided.")
        raise SystemExit(1)
    return link


def main(argv: list[str]) -> int:
    link = argv[1] if len(argv) > 1 else read_link_interactively()
    session_id = parse_session_id(link)

    session = requests.Session()
    page = fetch_reward_page(session, session_id)
    app_data = page["app_data"]
    security_token = page["security_token"]

    rewards = app_data.get("rewards", [])
    if len(rewards) != 3:
        print(f"{DIM}Note: expected 3 rewards, got {len(rewards)}.{RESET}")
    if not rewards:
        print("No rewards on this page. It may already be claimed or expired.")
        return 1

    print_rewards(app_data)

    auto_idx, reason = auto_select(rewards)
    if auto_idx is not None:
        option = auto_idx
        print(f"{BOLD}\033[32mAuto-pick:{RESET} option {option + 1} {DIM}({reason}){RESET}")
    else:
        print(f"{DIM}Manual pick ({reason}).{RESET}")
        option = prompt_choice(len(rewards))

    chosen = rewards[option]
    print(f"\nClaiming option {option + 1}: {format_reward(chosen)}")

    status, body = claim_reward(
        session,
        session_id=session_id,
        option=option,
        active_ad=int(app_data.get("activeAd", 0)),
        security_token=security_token,
    )

    body_preview = body.strip()
    if len(body_preview) > 200:
        body_preview = body_preview[:200] + "..."

    if 200 <= status < 300:
        print(f"{BOLD}\033[32m[OK] Claimed{RESET} (HTTP {status}) {DIM}{body_preview}{RESET}")
        return 0
    print(f"{BOLD}\033[31m[X] Failed{RESET} (HTTP {status})")
    print(body_preview)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(130)
