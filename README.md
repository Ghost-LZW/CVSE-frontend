# CVSE Frontend Display

Simplified CVSE video data display system that fetches real server data.

## Quick Start

### 1. Install Dependencies
```bash
pip install flask flask-cors pycapnp
```

### 2. Start Server
```bash
python quick_start.py
```

### 3. Access
- Frontend: http://localhost:5123
- API Data: http://localhost:5123/api/weekly-data

## File Description

- `index.html` - Frontend page
- `server.py` - Web server core code
- `quick_start.py` - Startup script
- `CVSE-GatheringTools/` - CVSE client library

## Features

- 📊 Display weekly video statistics
- 🎯 Filter videos by category
- 🔗 Click to jump to Bilibili page
- 📱 Responsive design