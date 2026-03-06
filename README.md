# CVSE Frontend Display

Simplified CVSE video data display system that fetches real server data.

## Quick Start

### 1. Install Dependencies
Install pdm: https://pdm-project.org/en/latest/
```bash
git submodule update --init --recursive
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

## TODO

- 添加 CORS 解决封面显示问题
- 完成皮卡挑选，预览校审（注意预览校审逻辑是如果有已经计算好的数据，直接展示，只有用户提出请求时才重新计算。重新计算开销极大，大约需要运行几分钟，需要合理设计/设置权限防止浪费服务器资源）