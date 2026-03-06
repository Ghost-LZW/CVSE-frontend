# CVSE Frontend Display

Simplified CVSE video data display system that fetches real server data.

## Quick Start

### 1. Install Dependencies
pdm: https://pdm-project.org/en/latest/
```bash
pdm install 
```

### 2. Start Server
Use `CVSE_SERVER_HOST`(default: "0.0.0.0") and `CVSE_SERVER_PORT`(default: "25123") to specify server configuration.
```bash
pdm run server
```

### 3. Access
- Frontend: http://localhost:25123
- API Data: http://localhost:25123/api/weekly-data

## File Description

- `index.html` - Frontend page
- `server.py` - Web server core code
- `quick_start.py` - Startup script
- `rpc_tools/` - CVSE client library

## Features

- 📊 Display weekly video statistics
- 🎯 Filter videos by category
- 🔗 Click to jump to Bilibili page
- 📱 Responsive design