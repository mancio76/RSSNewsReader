#!/usr/bin/env python3
"""
Server semplificato per RSSNewsReader API
"""

import sys
import os
import uvicorn

# Aggiungi il percorso root al PYTHONPATH
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

print("🚀 Starting RSSNewsReader API...")
print(f"📂 Project root: {project_root}")
print(f"🐍 Python path: {sys.path[0]}")

try:
    print("📦 Testing imports...")
    from app.api.main import app
    print("✅ Import successful!")
    
    print("🌐 Starting server...")
    print("📚 Documentation: http://127.0.0.1:8000/docs")
    print("❤️  Health check: http://127.0.0.1:8000/health")
    print("🛑 Press Ctrl+C to stop")
    print("=" * 50)
    
    # Avvia server con stringa di import per abilitare reload
    uvicorn.run(
        app,  # Usa stringa invece dell'oggetto
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
        reload_dirs=[project_root]  # Specifica directory per reload
    )
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("🔍 Debug info:")
    print(f"   Current directory: {os.getcwd()}")
    print(f"   Directory contents: {os.listdir('.')}")
    if os.path.exists('app'):
        print(f"   App directory contents: {os.listdir('app')}")
    sys.exit(1)
    
except KeyboardInterrupt:
    print("\n👋 Server stopped by user")
    
except Exception as e:
    print(f"❌ Server error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)