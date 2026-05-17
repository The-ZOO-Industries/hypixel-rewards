# hypixel-rewards

Claim your Hypixel daily reward from the terminal. No browser, just HTTP requests.

## Install

```powershell
pip install -r requirements.txt
```

## Use

```powershell
python claim.py
# or
python claim.py https://rewards.hypixel.net/claim-reward/<id>
```

Paste the reward link you got in-game (or just the trailing id). The script fetches the
page, parses the three reward choices, and prints them with their rarity.

### Auto-pick rules (in order)

1. **Souls** — if any option is souls, claim it.
   Exceptions that fall through to rule 2:
   - a real `LEGENDARY` reward is on offer (`dust` is treated as junk and doesn't block);
   - a `tokens` reward with `amount > 1` is on offer.
2. **Preferred coins** — coins from UHC Champions (`UHC`), Blitz SG (`SURVIVAL_GAMES`),
   or Mega Walls (`WALLS3`).
3. **Best rarity** — highest rarity (`LEGENDARY > EPIC > RARE > COMMON`); ties go to the
   first slot.

## How it works

1. `GET /claim-reward/<id>` — picks up the `_csrf` cookie, `window.securityToken`, and the
   inline `window.appData` JSON.
2. Prints the three rewards from `appData.rewards` and prompts for a choice.
3. `POST /claim-reward/claim?id=…&option=0|1|2&activeAd=…&_csrf=…` with the cookie jar
   from step 1 and a non-`rewardclaim` User-Agent.
4. Success is any 2xx response.
