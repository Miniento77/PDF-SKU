# Deployment Guide

This project can be deployed on another computer as a simple local web app.

## Option B: Run from GitHub on another machine

### Requirements
- Python 3.9+
- Git

### 1. Clone the repository
```bash
git clone <YOUR_GITHUB_REPO_URL>
cd label-pdf-sku
```

### 2. Create a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install the project
```bash
pip install -U pip
pip install -e .
```

This installs the declared runtime dependencies, including:
- `pypdf`
- `reportlab`

## 4. Start the web app

### Local-only access
```bash
python app.py --host 127.0.0.1 --port 8000
```
Open:
- `http://127.0.0.1:8000`

### LAN access (same local network)
```bash
python app.py --host 0.0.0.0 --port 8000
```
Then open from another device on the same network:
- `http://<THAT_COMPUTER_LOCAL_IP>:8000`

Example:
- `http://192.168.1.23:8000`

## 5. Use the app
1. Upload one shipping-label PDF
2. Enter SKU text such as:
   - `SF601 x2, BJ601DRY x1, DRSF601 x3`
3. Optionally expand **Advanced settings** to adjust layout
4. Generate and download the new PDF

## Updating on another machine
```bash
git pull
source .venv/bin/activate
pip install -e .
```

## Running tests
```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Recommended structure for broader access
If you want this tool available beyond one local machine:
- First deploy it to another always-on machine in your LAN
- Then optionally place it behind a reverse proxy
- If you have your own domain, use a subdomain such as:
  - `sku.yourdomain.com`
  - `label.yourdomain.com`

Your main website can keep using the main domain. A subdomain for this app will not conflict with the existing site.
