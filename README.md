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
page, parses the three reward choices, prints them with their rarity, and waits for you
to pick `1`, `2`, or `3` in the terminal before submitting the claim.

## How it works

1. `GET /claim-reward/<id>` — picks up the `_csrf` cookie, `window.securityToken`, and the
   inline `window.appData` JSON.
2. Prints the three rewards from `appData.rewards` and prompts for a choice.
3. `POST /claim-reward/claim?id=…&option=0|1|2&activeAd=…&_csrf=…` with the cookie jar
   from step 1 and a non-`rewardclaim` User-Agent.
4. Success is any 2xx response.
