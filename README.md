# 🎬 Netflix Cookie Checker

A powerful, multi-threaded Netflix cookie validator that checks cookie validity, extracts account information, and organizes results efficiently.

## ✨ Features

- 🚀 **Multi-threaded Processing** - Fast concurrent cookie validation
- 🌐 **Proxy Support** - Rotate through multiple proxies to avoid rate limiting
- 📊 **Detailed Account Info** - Extract plan details, country, member status, and more
- 🔄 **Auto Format Conversion** - Convert JSON cookies to Netscape format
- 📁 **Smart Organization** - Automatically sort results into different folders
- 🔍 **Duplicate Detection** - Prevent duplicate accounts using User GUID tracking
- 📈 **Real-time Statistics** - Live progress tracking and final results
- 🎨 **Colorful Interface** - Beautiful console output with status indicators

## 📋 Requirements

```
pip install requests colorama
```

## 🚀 Quick Start

1. **Clone the repository**
```
git clone https://github.com/harshitkamboj/netflix-cookie-checker.git
cd netflix-cookie-checker
```

3. **Install dependencies**
```
pip install -r requirements.txt
```

5. **Setup your files**
   - Add your Netflix cookies (`.txt` or `.json` format) to the `cookies/` folder
   - Add proxies to `proxy.txt` (optional but recommended)

6. **Run the checker**
```
python main.py
```

## 📁 Folder Structure

```
├── cookies/ # Input folder for your cookies
├── hits/ # Working subscribed accounts
├── free/ # Working but unsubscribed accounts
├── failures/ # Invalid/expired cookies
├── broken/ # Malformed cookie files
├── json_cookies_after_conversion/ # Processed JSON files
├── proxy.txt # Your proxy list (optional)
└── main.py # Main script
```

## 🍪 Cookie Formats Supported

### Netscape Format (.txt)
```.netflix.com TRUE / FALSE 1234567890 cookie_name cookie_value```

### JSON Format (.json)
```
[
{
"domain": ".netflix.com",
"flag": "TRUE",
"path": "/",
"secure": false,
"expiration": "1234567890",
"name": "cookie_name",
"value": "cookie_value"
}
]
```

## 🌐 Proxy Setup

Create a `proxy.txt` file with your proxies (one per line):

```
ip:port
user:pass@ip:port
http://ip:port
http://user:pass@ip:port
```

## 📊 Output Examples

### Working Subscribed Account (hits/)
```
Filename: 4_US_github-harshitkamboj_True_abc123.txt

Max Streams: 4 Screens
Plan: Premium
Country: US
Member Since: January 2023
Extra members: Yes✅
Checker By: github.com/harshitkamboj
Netflix Cookie 👇

[original cookie content]
```

### Working Free Account (free/)
```
Filename: PaymentM-False_US_github-harshitkamboj_xyz789.txt

Payment Method: False
Country: US
Checker By: github.com/harshitkamboj
Netflix Cookie 👇

[original cookie content]
```

## ⚙️ Configuration

You can modify these settings in the script:

- **Thread Count**: Change `num_threads` parameter (default: 20)
- **Timeout**: Modify request timeout (default: 30 seconds)
- **Retry Strategy**: Adjust retry attempts and backoff

## 📈 Statistics

The checker provides detailed statistics:
- 📈 Total cookies checked
- ✅ Working subscribed accounts
- ❌ Working but unsubscribed accounts  
- 💀 Dead/expired cookies

## 🔧 Advanced Features

### Duplicate Prevention
- Automatically detects duplicate accounts using User GUID
- Generates unique identifiers for unknown users
- Prevents storage of duplicate results

### Smart Error Handling
- Handles malformed cookies gracefully
- Proxy fallback mechanism
- Automatic retry on network errors

### Account Information Extraction
- Plan type and pricing tier
- Country of registration
- Member since date
- Maximum concurrent streams
- Extra member availability
- Payment method status

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## ⚠️ Disclaimer

This tool is for educational purposes only. Please ensure you have permission to test the cookies you're using. Respect Netflix's terms of service and rate limits.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🌟 Support

If you found this tool helpful, please:
- ⭐ Star this repository
- 🍴 Fork and share with others
- 🐛 Report any issues you find
- 💡 Suggest new features

## 📞 Contact

- **GitHub**: [@harshitkamboj](https://github.com/harshitkamboj)
- **Discord**: illuminatis69

---

<div align="center">
  <b>Made with ❤️</b>
  <br>
  <i>Star ⭐ this repo if you found it useful!</i>
</div>

