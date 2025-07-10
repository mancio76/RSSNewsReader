#!/usr/bin/env python3
"""
Server script per avviare l'API REST di RSSNewsReader
"""

import sys
import os
import uvicorn
import argparse
import logging

# Aggiungi il percorso root del progetto al PYTHONPATH
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Verifica che il modulo app sia accessibile
try:
    from app.api.main import app
    print("✅ Modulo app.api.main caricato correttamente")
except ImportError as e:
    print(f"❌ Errore importazione modulo: {e}")
    print(f"📂 Directory corrente: {os.getcwd()}")
    print(f"📂 Project root: {project_root}")
    print(f"📂 Contenuto directory:")
    for item in os.listdir(project_root):
        print(f"   - {item}")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="RSSNewsReader API Server")
    parser.add_argument(
        "--host", 
        default="127.0.0.1", 
        help="Host address (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000, 
        help="Port number (default: 8000)"
    )
    parser.add_argument(
        "--reload", 
        action="store_true", 
        help="Enable auto-reload for development"
    )
    parser.add_argument(
        "--workers", 
        type=int, 
        default=1, 
        help="Number of worker processes (default: 1)"
    )
    parser.add_argument(
        "--log-level", 
        choices=["debug", "info", "warning", "error"], 
        default="info",
        help="Log level (default: info)"
    )
    parser.add_argument(
        "--access-log", 
        action="store_true", 
        help="Enable access log"
    )
    
    args = parser.parse_args()
    
    # Configurazione logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    
    print("🚀 Starting RSSNewsReader API Server")
    print("=" * 50)
    print(f"📡 Host: {args.host}")
    print(f"🔌 Port: {args.port}")
    print(f"📝 Log Level: {args.log_level}")
    print(f"🔄 Auto-reload: {args.reload}")
    print(f"👥 Workers: {args.workers}")
    print("=" * 50)
    print(f"📚 API Documentation: http://{args.host}:{args.port}/docs")
    print(f"📖 ReDoc: http://{args.host}:{args.port}/redoc")
    print(f"❤️  Health Check: http://{args.host}:{args.port}/health")
    print("=" * 50)
    
    try:
        # Avvia server usando l'app importata
        uvicorn.run(
            app,  # Usa l'app importata direttamente
            host=args.host,
            port=args.port,
            reload=args.reload,
            workers=args.workers if not args.reload else 1,  # reload non funziona con workers > 1
            log_level=args.log_level,
            access_log=args.access_log
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()