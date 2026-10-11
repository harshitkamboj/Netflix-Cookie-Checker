# Netflix Cookie Checker v4.6

A multi-threaded Netflix cookie checker with configurable account details, PC/mobile/TV login links, plan-based output folders, and Discord/Telegram notifications.

## Downloads

- [EXE releases](https://github.com/harshitkamboj/Netflix-Cookie-Checker/releases)
- [Latest published release](https://github.com/harshitkamboj/Netflix-Cookie-Checker/releases/latest)
- [Discord community](https://discord.gg/DYJFE9nu5X)

## What's New in v4.6

### New features

- **TV Login links:** added `📺 TV Login` alongside PC and mobile links in saved TXT files and Discord/Telegram notifications.
- **Choose any devices:** use `"pc"`, `"mobile"`, or `"tv"` individually, or select two with `"pc/tv"`, `"pc/mobile"`, or `"mobile/tv"`.
- **All devices in one setting:** `nftoken: true` or `nftoken: "all"` includes PC, mobile, and TV links.
- **Consistent notification output:** the selected devices appear in `full` and `nftoken` notification modes when token generation succeeds. The `cookie` mode remains cookie-only.

### Fixes and compatibility

- Fixed NFToken mode handling so TV and slash-separated selections produce the requested links instead of falling back to PC + mobile.
- Device combinations accept mixed case, surrounding spaces, and either device order; repeated devices produce only one link.
- Preserved `"both"` as the legacy PC + mobile option; `false` still disables NFToken generation.
- Corrected the README's on-hold folder layout and extra-member descriptions to match the checker.

### Example

```yml
nftoken: true # All three devices: PC, mobile, and TV
# Alternatively: "pc", "mobile", "tv", "pc/tv", "pc/mobile", "mobile/tv", or false
# Case-insensitive; legacy "both" means PC + mobile.
```

TV link format: `https://netflix.com/tv2?nftoken=...`. The TV emoji follows the existing `add_emojis` setting.

## Features

- **Flexible NFToken login links:** optional generation with PC, mobile, TV, or selected device combinations, plus an expiry timestamp in the output.
- **Detailed account information:** plan, country, quality, streams, price, billing date, payment details, profiles, and other fields controlled through `txt_fields`.
- **Discord and Telegram notifications:** `full`, `cookie`, and `nftoken` modes, with plan filters and configurable emoji labels.
- **Organized results:** separate folders for each run, plan, free accounts, duplicates, and extra-member accounts; on-hold accounts go into their plan's `On Hold/` subfolder.
- **Flexible cookie input:** Netscape TXT and JSON formats, including multiple Netflix cookie bundles in one file.
- **Configurable checking:** multiple worker threads, request timeout, retry counts, optional fallback account page, and optional retries for incomplete account information.
- **Proxy support:** HTTP, HTTPS, and SOCKS schemes, authenticated proxy formats, and proxy rotation between retries when proxies are available.
- **Duplicate detection:** filters repeated accounts within a run using email or account identifier.
- **Clear progress display:** compact dashboard or per-result logs, plan counts, and status counters for hits, free accounts, duplicates, on-hold accounts, failures, and errors.
- **Automatic setup recovery:** recreates missing configuration, proxy file, and required folders.

## Previous Release: v4.5

- Added on-hold output routing and an `OnHold` counter.
- Hid the unknown-plan counter until an unknown account is found.
- Added separate emoji modes for TXT files and notification messages.
- Improved cookie-name casing normalization and hold-status extraction.

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
output/run_.../Premium/On Hold/
output/run_.../Standard/On Hold/
output/run_.../Basic/On Hold/
output/run_.../Mobile/On Hold/
output/run_.../Unknown/   # created only when needed
failed/
broken/
proxy.txt
config.yml
main.py
```

Extra-member accounts are saved in their corresponding `<Plan> (Extra Member)/` folder.
On-hold folders use `<Plan>/On Hold/` and are created only when an on-hold subscribed account is found.

Processed source cookie files are moved or removed as results are saved. Keep a backup if you need the original input files.

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
- `nftoken`: `false` to disable; `true` or `"all"` for all three devices; `"pc"`, `"mobile"`, or `"tv"` for one device; slash-separated combinations such as `"pc/tv"` for two. Values are case-insensitive; legacy `"both"` still means PC + mobile.
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

nftoken: false # false = disabled; true or "all" = PC, mobile, and TV links
# Select one: "pc", "mobile", "tv"; combine with "/": "pc/tv", "pc/mobile", "mobile/tv".
# Values are case-insensitive; legacy "both" = "pc/mobile".
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

| `nftoken` value | Included login links |
| --- | --- |
| `false` | Disabled |
| `true` or `"all"` | PC, mobile, and TV |
| `"pc"` | PC only |
| `"mobile"` | Mobile only |
| `"tv"` | TV only |
| `"pc/tv"` | PC and TV |
| `"pc/mobile"` | PC and mobile |
| `"mobile/tv"` | Mobile and TV |
| `"both"` | PC and mobile (legacy option) |

Device names are case-insensitive. Combinations may be written in either order, such as `"TV/PC"`.

- PC: `https://netflix.com/?nftoken=...`
- Mobile: `https://netflix.com/unsupported?nftoken=...`
- TV: `https://netflix.com/tv2?nftoken=...`

Selected links are included in saved TXT output for subscribed accounts when token generation succeeds. They also appear in enabled Discord/Telegram notifications using `full` or `nftoken` mode, subject to the configured plan filters. The `cookie` notification mode sends cookies without login links. Emoji display follows `add_emojis`.

NFToken generation is disabled in the default configuration. Setting `performance.nftoken_for_free: true` permits token-generation requests for free accounts, but their current TXT and notification formatting does not include those links.

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
