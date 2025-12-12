# Phaenon Coordinate Interceptor

A Windows tool with a PySide6 GUI that runs a local MITM proxy to capture latitude/longitude coordinates from HTTPS JS traffic and convert them offline to **country + city** using `reverse_geocoder`. Captures trigger a Windows 10 toast notification with sound and a custom icon.

---

## Features

- Integrated mitmproxy backend
- PySide6 GUI with:
  - Live match list
  - Log output
  - Proxy status
- Offline reverse geolocation (country + city)
- Saves matches to `captures.csv`
- Windows 10 toast notifications with sound and custom icon for every capture

---

## Installation

Install Python 3.10–3.12.

Install dependencies:

```
pip install -r requirements.txt
```

---

## Running

```
python gui.py
```

1. Click **Start Proxy**  
2. Set your browser/system proxy to:

```
HTTP Proxy:  127.0.0.1:8080
HTTPS Proxy: 127.0.0.1:8080
```

Matches appear in the GUI, log, CSV, and trigger a Windows 10 notification.

---

## Output

CSV format:

```
timestamp, url, lat, lng, country, city
```

---

## Notes

- Install the mitmproxy certificate if HTTPS traffic fails:
```
http://mitm.it
```
- Only Windows 10 is supported for notifications.
- Icon file should be located at `assets/icon.ico`.

---

## License

MIT
