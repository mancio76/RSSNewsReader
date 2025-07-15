###!/usr/bin/env python3
"""
Server senza reload per RSSNewsReader API
"""

import sys
import os
import uvicorn
import signal
import threading
import time
import datetime as dt
import logging
import logging.config

# Aggiungi il percorso root al PYTHONPATH
project_root = os.path.dirname(os.path.abspath(__file__))
project_file = os.path.splitext(os.path.basename(__file__))[0]
sys.path.insert(0, project_root)

# Flag per controllo del server
server_running = True
server_starttime = dt.datetime.now(dt.timezone.utc)
logger = logging.getLogger(project_file)
logging.config.fileConfig('logging.ini')
fileHandler = logging.FileHandler(filename=f'{project_file}.log', encoding='utf-8')
fileformatter = logging.Formatter('%(levelname)s:     %(asctime)s - %(name)s - %(message)s')
fileHandler.setFormatter(fileformatter)
logger.addHandler(fileHandler)

# create console handler and set level to debug
##ch = logging.StreamHandler()
##ch.setLevel(logging.DEBUG)

# create formatter
##formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# add formatter to ch
##ch.setFormatter(formatter)

# add ch to logger
##logger.addHandler(ch)

logger.info(f"Server started at {server_starttime.isoformat()}")

def signal_handler(signum, frame):
    global server_running
    print(f"\n🛑 Received signal {signum}, shutting down...")
    logger.info("\n🛑 Received signal {signum}, shutting down...")
    server_running = False

def keep_alive():
    """Mantiene il thread principale attivo"""
    global server_running
    try:
        while server_running:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("👋 Server stopped by user")
        print("\n👋 Server stopped by user")
        server_running = False
        
logger.info("🚀 Starting RSSNewsReader API...")
logger.info(f"📂 Project root: {project_root}")

##print("🚀 Starting RSSNewsReader API...")
##print(f"📂 Project root: {project_root}")

try:
    logger.info("📦 Testing imports...")
    from app.api.main import app
    logger.info("✅ Import successful!")
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("🌐 Starting server...")
    logger.info("📚  Documentation: http://127.0.0.1:8000/docs")
    logger.info("❤️  Health check: http://127.0.0.1:8000/health")
    logger.info("🚀  Application: http://127.0.0.1:8000/web")
    print("🛑  Press Ctrl+C to stop")
    print("=" * 50)
    
    # Configura uvicorn
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info",
        access_log=True
    )
    
    server = uvicorn.Server(config)
    
    # Avvia server in thread separato
    server_thread = threading.Thread(target=server.run)
    server_thread.daemon = True
    server_thread.start()
    
    logger.info("✅ Server started successfully!")
    logger.info("🔄 Server running in background...")
    
    # Mantieni il main thread attivo
    keep_alive()
    
    print("🔄 Shutting down server...")
    logger.info("🔄 Shutting down server...")
    server.should_exit = True
    server_thread.join(timeout=5)
    
except ImportError as e:
    logger.error(f"❌ Import error: {e}")
    logger.error("🔍 Debug info:")
    logger.error(f"   Current directory: {os.getcwd()}")
    logger.error(f"   Directory contents: {os.listdir('.')}")
    if os.path.exists('app'):
        logger.error(f"   App directory contents: {os.listdir('app')}")
    sys.exit(1)
    
except Exception as e:
    logger.error(f"❌ Server error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("👋 Server shutdown complete")
logger.info("👋 Server shutdown complete")