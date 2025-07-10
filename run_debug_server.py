#!/usr/bin/env python3
"""
Script di debug per identificare problemi di avvio
"""

import sys
import os
import traceback

def debug_environment():
    print("🔍 DEBUGGING ENVIRONMENT")
    print("=" * 50)
    
    # Info base
    print(f"Python version: {sys.version}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Script location: {os.path.abspath(__file__)}")
    
    # Contenuto directory
    print(f"\n📂 Current directory contents:")
    for item in sorted(os.listdir('.')):
        item_path = os.path.join('.', item)
        item_type = "DIR" if os.path.isdir(item_path) else "FILE"
        print(f"   {item_type}: {item}")
    
    # Check app directory
    if os.path.exists('app'):
        print(f"\n📂 App directory contents:")
        for item in sorted(os.listdir('app')):
            item_path = os.path.join('app', item)
            item_type = "DIR" if os.path.isdir(item_path) else "FILE"
            print(f"   {item_type}: {item}")
            
        if os.path.exists('app/api'):
            print(f"\n📂 App/api directory contents:")
            for item in sorted(os.listdir('app/api')):
                item_path = os.path.join('app/api', item)
                item_type = "DIR" if os.path.isdir(item_path) else "FILE"
                print(f"   {item_type}: {item}")
    
    # Python path
    print(f"\n🐍 Python path:")
    for i, path in enumerate(sys.path):
        print(f"   {i}: {path}")

def test_imports():
    print("\n🧪 TESTING IMPORTS")
    print("=" * 50)
    
    # Test base imports
    try:
        import fastapi
        print(f"✅ FastAPI: {fastapi.__version__}")
    except ImportError as e:
        print(f"❌ FastAPI: {e}")
        return False
    
    try:
        import uvicorn
        print(f"✅ Uvicorn: {uvicorn.__version__}")
    except ImportError as e:
        print(f"❌ Uvicorn: {e}")
        return False
    
    try:
        import sqlalchemy
        print(f"✅ SQLAlchemy: {sqlalchemy.__version__}")
    except ImportError as e:
        print(f"❌ SQLAlchemy: {e}")
        return False
    
    # Test app imports
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)
    
    try:
        import app
        print("✅ App package imported")
    except ImportError as e:
        print(f"❌ App package: {e}")
        return False
    
    try:
        from app import models
        print("✅ App.models imported")
    except ImportError as e:
        print(f"❌ App.models: {e}")
        return False
    
    try:
        from app import api
        print("✅ App.api imported")
    except ImportError as e:
        print(f"❌ App.api: {e}")
        return False
    
    try:
        from app.api import main
        print("✅ App.api.main imported")
    except ImportError as e:
        print(f"❌ App.api.main: {e}")
        print(f"   Traceback: {traceback.format_exc()}")
        return False
    
    try:
        from app.api.main import app as fastapi_app
        print("✅ FastAPI app imported")
        print(f"   App type: {type(fastapi_app)}")
    except ImportError as e:
        print(f"❌ FastAPI app: {e}")
        print(f"   Traceback: {traceback.format_exc()}")
        return False
    
    return True

def test_database():
    print("\n💾 TESTING DATABASE")
    print("=" * 50)
    
    try:
        from app.models.base import create_tables, SessionLocal
        print("✅ Database models imported")
        
        # Test database creation
        create_tables()
        print("✅ Database tables created/verified")
        
        # Test database connection
        db = SessionLocal()
        try:
            from app.models import Source
            count = db.query(Source).count()
            print(f"✅ Database connection: {count} sources found")
        finally:
            db.close()
            
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        print(f"   Traceback: {traceback.format_exc()}")
        return False

def main():
    print("🚀 RSSNewsReader API Debug Tool")
    print("=" * 50)
    
    debug_environment()
    
    if not test_imports():
        print("\n❌ Import tests failed. Cannot proceed.")
        return
    
    if not test_database():
        print("\n❌ Database tests failed. Cannot proceed.")
        return
    
    print("\n✅ ALL TESTS PASSED!")
    print("\nTry running the server with:")
    print("   python simple_server.py")
    print("   or")
    print("   uvicorn app.api.main:app --reload")

if __name__ == "__main__":
    main()