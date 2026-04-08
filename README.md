# Netflix Cookie Checker V4.5

Fast multi-threaded Netflix cookie checker with speed controls, extra-member separation, on-hold plan routing, flexible emoji modes, and richer Telegram/Discord formatting.

## Download EXE

- Releases: https://github.com/harshitkamboj/Netflix-Cookie-Checker/releases
- Latest release: https://github.com/harshitkamboj/Netflix-Cookie-Checker/releases/latest
- Discord: https://discord.gg/DYJFE9nu5X

## What Is New In V4.5

- On-hold subscribed accounts are now routed to `output/run_.../On Hold/<Plan>/`
- Added `OnHold` counter in console summary and title output
- `Unknown` plan line is hidden in console until at least one unknown account exists
- New `add_emojis` config mode: `false`, `"txt"`, `"webhook"`, `"both"` (`true` => `"both"`)
- Emoji behavior is now configurable separately for txt vs notification messages
- Cookie parsing normalizes cookie-name casing more reliably
- Hold-status extraction improved for additional GraphQL/fallback patterns

## Features

- Fast multi-threaded cookie checking
- Supports Netscape `.txt` and JSON cookie formats
- Detailed account extraction with configurable txt fields
- Optional NFToken generation with mode-specific links
- Strong proxy support with retry rotation on retryable errors
- Broad proxy format support including SOCKS schemes
- Duplicate filtering to avoid repeated hits
- Organized output by run and plan bucket
- Discord and Telegram notifications (`full`, `cookie`, `nftoken`)
- Display modes: `log` and `simple`
- Auto-recovery for missing config/proxy/folders

## Requirements

```bash
pip install -r requirements.txt
```

Optional for SOCKS proxies:

```bash
pip install requests[socks]
```

## Quick Start

1. Clone the repo.

```bash
git clone https://github.com/harshitkamboj/Netflix-Cookie-Checker.git
cd Netflix-Cookie-Checker
```

2. Install dependencies.

```bash
pip install -r requirements.txt
```

3. Put cookie files in `cookies/`.
4. Optionally add proxies in `proxy.txt`.
5. Edit `config.yml` if needed.
6. Run:

```bash
python main.py
```

## Output Layout

```text
cookies/
output/
output/run_YYYY-MM-DD_HH-MM-SS/
output/run_.../Premium/
output/run_.../Premium (Extra Member)/
output/run_.../Standard/
output/run_.../Standard With Ads/
output/run_.../Basic/
output/run_.../Mobile/
output/run_.../Free/
output/run_.../Duplicate/
output/run_.../On Hold/Premium/
output/run_.../On Hold/Standard/
output/run_.../On Hold/Basic/
output/run_.../On Hold/Mobile/
output/run_.../Unknown/   # created only when needed
failed/
broken/
proxy.txt
config.yml
main.py
```

Extra-member accounts are saved only in `Premium (Extra Member)`.
On-hold folders are created only when at least one on-hold subscribed account is found.

## Supported Cookie Formats

### Netscape (`.txt`)

```text
.netflix.com  TRUE  /  TRUE  1234567890  NetflixId  xxx
.netflix.com  TRUE  /  TRUE  1234567890  SecureNetflixId  xxx
.netflix.com  TRUE  /  TRUE  1234567890  nfvdid  xxx
```

### JSON (`.json`)

```json
[
  {
    "domain": ".netflix.com",
    "path": "/",
    "secure": true,
    "expirationDate": 1234567890,
    "name": "NetflixId",
    "value": "xxx"
  }
]
```

## Proxy Formats

One per line in `proxy.txt`:

```text
ip:port
user:pass@ip:port
ip:port@user:pass
http://ip:port
http://user:pass@ip:port
https://user:pass@ip:port
socks4://user:pass@ip:port
socks4a://user:pass@ip:port
socks5://user:pass@ip:port
socks5h://user:pass@ip:port
ip:port:user:pass
user:pass:ip:port
ip:port user:pass
ip:port|user:pass
ip:port;user:pass
ip:port,user:pass
```

Also accepted and normalized:

```text
http:/ip:port
```

## Config

### Main sections

- `txt_fields`: controls which lines are written to output txt
- `nftoken`: `false`, `"pc"`, `"mobile"`, `"both"` (or `true` as `"both"`)
- `add_emojis`: controls emoji labels in txt and/or webhook/Telegram messages
- `notifications`: Discord webhook and Telegram settings
- `display`: console mode (`log` or `simple`)
- `retries`: retry counts for network/proxy and NFToken requests
- `performance`: speed/reliability tradeoff options

### Default example

```yml
txt_fields:
  name: false
  email: false
  plan: true
  country: true
  member_since: false
  quality: true
  max_streams: true
  plan_price: true
  next_billing: true
  payment_method: true
  card: false
  phone: false
  hold_status: false
  extra_members: true
  email_verified: false
  membership_status: false
  profiles: true
  user_guid: false

nftoken: false # false | "pc" | "mobile" | "both" (true => "both")
add_emojis: "webhook" # false | "txt" | "webhook" | "both" (true => "both")

notifications:
  webhook:
    enabled: false
    url: ""
    mode: "full" # full | cookie | nftoken
    plans: "all"
  telegram:
    enabled: false
    bot_token: ""
    chat_id: ""
    mode: "full" # full | cookie | nftoken
    plans: "all"

display:
  mode: "simple" # log | simple

retries:
  error_proxy_attempts: 3
  nftoken_attempts: 1

performance:
  request_timeout_seconds: 15
  fallback_account_page: false
  retry_incomplete_info: false
  nftoken_for_free: false
```

## NFToken Mode Links

- `pc`: `https://netflix.com/?nftoken=...`
- `mobile`: `https://netflix.com/unsupported?nftoken=...`
- `both`: sends both links in Discord/Telegram/txt

## Notification Labels

Emoji labels are controlled by `add_emojis`:

- `false`: no emojis in txt or notifications
- `"txt"`: emojis only in saved txt output
- `"webhook"`: emojis only in Discord/Telegram notifications
- `"both"` or `true`: emojis in both txt and notifications

## Retry Behavior

- Retries per cookie: `retries.error_proxy_attempts`
- Proxy rotates between retries when available
- Retryable HTTP statuses: `403`, `429`, `500`, `502`, `503`, `504`
- Retry-exhausted retryable cases go to `broken/`
- Invalid/dead cookies go to `failed/`

## Auto-Recovery

- Recreates missing `config.yml`, `proxy.txt`, `cookies/`, `output/`, `failed/`, `broken/`
- If config is invalid, it is replaced with the default commented config

## Contact

- GitHub: https://github.com/harshitkamboj
- Website: https://harshitkamboj.in
- Discord username: `illuminatis69`
- Discord profile: https://discord.com/users/1171797848078172173
- Discord: https://discord.gg/DYJFE9nu5X

## License

MIT License. See `LICENSE`.

## Disclaimer

Educational use only. Use only on accounts and cookies you are authorized to test.
