#!/usr/bin/env python3
"""Test delle dipendenze"""

def test_imports():
    try:
        import fastapi
        print(f"✅ FastAPI: {fastapi.__version__}")
        
        import uvicorn
        print(f"✅ Uvicorn: {uvicorn.__version__}")
        
        import sqlalchemy
        print(f"✅ SQLAlchemy: {sqlalchemy.__version__}")
        
        import aiohttp
        print(f"✅ aiohttp: {aiohttp.__version__}")
        
        from bs4 import BeautifulSoup
        print(f"✅ BeautifulSoup4: disponibile")
        
        import feedparser
        print(f"✅ feedparser: {feedparser.__version__}")
        
        import jinja2
        print(f"✅ Jinja2: {jinja2.__version__}")
        
        from dateutil import parser
        print(f"✅ python-dateutil: disponibile")
        
        print("\n🎉 Tutte le dipendenze sono installate correttamente!")
        return True
        
    except ImportError as e:
        print(f"❌ Errore import: {e}")
        return False

if __name__ == "__main__":
    test_imports()