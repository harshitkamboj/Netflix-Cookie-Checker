# Netflix Cookie Checker V3

Fast multi-threaded Netflix cookie checker with broad cookie parsing, proxy retry rotation, NFToken generation, detailed account extraction, and Discord/Telegram notifications.

## Download

Download the latest Windows build if you do not want to run Python:

- Releases: https://github.com/harshitkamboj/Netflix-Cookie-Checker/releases
- Latest release: https://github.com/harshitkamboj/Netflix-Cookie-Checker/releases/latest
- Discord server: https://discord.gg/DYJFE9nu5X

## Features

- Fast multi-threaded cookie checking
- Supports Netscape `.txt` and JSON cookie formats
- Detailed account extraction with clean hit output
- Optional NFToken generation for quick login access
- Strong proxy support with retry rotation on bad responses
- Broad proxy format support including auth and SOCKS formats
- Clean duplicate filtering to avoid repeated hits
- Clear result separation for subscribed, free, duplicate, failed, and broken
- Organized output by run folder and plan type
- Discord and Telegram notifications
- Two display modes: `log` and `simple`
- Configurable txt output fields for cleaner saved results
- Auto-recreates missing config, proxy file, and working folders

## Requirements

```bash
pip install -r requirements.txt
```

Optional for SOCKS proxies:

```bash
pip install requests[socks]
```

## Quick Start

1. Clone the repo:

```bash
git clone https://github.com/harshitkamboj/Netflix-Cookie-Checker.git
cd Netflix-Cookie-Checker
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Put cookie files in `cookies/`
4. Optionally add proxies in `proxy.txt`
5. Edit `config.yml` if needed
6. Run:

```bash
python main.py
```

## Folder Layout

```text
cookies/                # input cookies
output/                 # checked results
output/run_YYYY-MM-DD.../
output/run_.../Premium/
output/run_.../Standard/
output/run_.../Standard With Ads/
output/run_.../Basic/
output/run_.../Mobile/
output/run_.../Free/
output/run_.../Duplicate/
failed/                 # invalid / incomplete cookies
broken/                 # malformed / retry-exhausted / proxy-error cases
proxy.txt
config.yml
main.py
```

## Supported Cookie Formats

### Netscape (`.txt`)

```text
.netflix.com	TRUE	/	TRUE	1234567890	NetflixId	xxx
.netflix.com	TRUE	/	TRUE	1234567890	SecureNetflixId	xxx
.netflix.com	TRUE	/	TRUE	1234567890	nfvdid	xxx
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

### Main Sections

- `txt_fields`: controls which fields are written into output txt files
- `nftoken`: enables or disables NFToken generation
- `notifications`: Discord / Telegram settings and mode
- `display`: console UI mode (`log` or `simple`)
- `retries`: retry counts for retryable request and proxy errors

### Default Example

```yml
txt_fields:
  plan: true
  country: true
  quality: true
  max_streams: true
  next_billing: true
  payment_method: true
  extra_members: true
  profiles: true

nftoken: false

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
```

### Advanced TXT Fields

You can enable these for more detailed output:

- `name`
- `email`
- `member_since`
- `card`
- `phone`
- `hold_status`
- `email_verified`
- `membership_status`
- `user_guid`

## Notification Modes

### `full`

- Sends formatted account details
- Sends the output txt file as the attachment

### `cookie`

- Sends formatted account details in the message
- Sends the raw cookie content as the attachment

### `nftoken`

- Sends only the generated NFToken link
- Includes estimated expiry in UTC

## Retry Behavior

- Retries per cookie: `retries.error_proxy_attempts`
- Rotates proxies across retries when available
- Retryable status codes: `403`, `429`, `500`, `502`, `503`, `504`
- Retryable failures exhausted move to `broken/`
- Invalid or dead cookies move to `failed/`

## Output Notes

- Output is grouped into per-run folders under `output/`
- Plan folders are created automatically (`Premium`, `Standard`, `Standard With Ads`, `Basic`, `Mobile`, `Free`, `Duplicate`)
- Full output txt includes account details, NFTokens (if enabled), and the cookie block
- NFToken expiry is written as an estimated 1-hour UTC timestamp

## Auto-Recovery

- If `config.yml` is missing, it is recreated automatically
- If `config.yml` is invalid, it is replaced with the default commented config
- If `cookies`, `output`, `failed`, or `broken` are missing, they are recreated automatically
- If `proxy.txt` is missing, it is recreated automatically with examples

## Contact

- GitHub: https://github.com/harshitkamboj
- Website: https://harshitkamboj.in
- Discord username: `illuminatis69`
- Discord server: https://discord.gg/DYJFE9nu5X

## License

MIT License. See `LICENSE`.

## Disclaimer

Educational use only. Use only on accounts and cookies you are authorized to test.
