"""
Verify that all dependencies are properly installed.
Run this script to check if your environment is set up correctly.
"""

import sys
from pathlib import Path

def check_import(module_name, package_name=None):
    """Check if a module can be imported."""
    try:
        __import__(module_name)
        print(f"✅ {package_name or module_name}")
        return True
    except ImportError as e:
        print(f"❌ {package_name or module_name}: {e}")
        return False

def main():
    print("🔍 Checking Python environment for web crawler...")
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version}")
    print()
    
    # Check if we're in the right directory
    if not Path("main.py").exists():
        print("❌ Not in the correct directory. Please run from the crawler project root.")
        return False
        
    print("📦 Checking required packages:")
    
    # List of required imports
    checks = [
        ("yaml", "PyYAML"),
        ("rich", "rich"),
        ("httpx", "httpx"),
        ("bs4", "beautifulsoup4"),
        ("lxml", "lxml"),
        ("pypdf", "pypdf"),
        ("pdfminer", "pdfminer.six"),
        ("dotenv", "python-dotenv"),
        ("tqdm", "tqdm"),
        ("pydantic", "pydantic"),
        ("openai", "openai"),
        ("pinecone", "pinecone-client"),
        ("yarl", "yarl"),
    ]
    
    all_good = True
    for module, package in checks:
        if not check_import(module, package):
            all_good = False
    
    print()
    
    if all_good:
        print("🎉 All packages are installed correctly!")
        print("You can now run: python main.py --dry-run")
    else:
        print("❌ Some packages are missing.")
        print("Please run: pip install -r requirements.txt")
        print()
        print("If you're getting import errors, make sure you've activated the virtual environment:")
        print("  Windows PowerShell: .venv\\Scripts\\Activate.ps1")
        print("  Windows CMD: .venv\\Scripts\\activate.bat")
    
    return all_good

if __name__ == "__main__":
    main()