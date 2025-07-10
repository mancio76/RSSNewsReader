#!/usr/bin/env python3
"""
Server senza reload per RSSNewsReader API
"""

import sys
import os
import uvicorn
import signal
import threading
import time

# Aggiungi il percorso root al PYTHONPATH
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Flag per controllo del server
server_running = True

def signal_handler(signum, frame):
    global server_running
    print(f"\n🛑 Received signal {signum}, shutting down...")
    server_running = False

def keep_alive():
    """Mantiene il thread principale attivo"""
    global server_running
    try:
        while server_running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
        server_running = False

print("🚀 Starting RSSNewsReader API...")
print(f"📂 Project root: {project_root}")

try:
    print("📦 Testing imports...")
    from app.api.main import app
    print("✅ Import successful!")
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("🌐 Starting server...")
    print("📚  Documentation: http://127.0.0.1:8000/docs")
    print("❤️  Health check: http://127.0.0.1:8000/health")
    print("🚀  Application: http://127.0.0.1:8000/web")
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
    
    print("✅ Server started successfully!")
    print("🔄 Server running in background...")
    
    # Mantieni il main thread attivo
    keep_alive()
    
    print("🔄 Shutting down server...")
    server.should_exit = True
    server_thread.join(timeout=5)
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("🔍 Debug info:")
    print(f"   Current directory: {os.getcwd()}")
    print(f"   Directory contents: {os.listdir('.')}")
    if os.path.exists('app'):
        print(f"   App directory contents: {os.listdir('app')}")
    sys.exit(1)
    
except Exception as e:
    print(f"❌ Server error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("👋 Server shutdown complete")