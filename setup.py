import subprocess
import sys
import os

def install_requirements():
    """Install Python requirements"""
    print("Installing Python packages...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    print("✅ Python packages installed")

def install_playwright():
    """Install Playwright browsers"""
    print("Installing Playwright browsers...")
    subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
    print("✅ Playwright browsers installed")

def create_config():
    """Create config.py from example if it doesn't exist"""
    if not os.path.exists("config.py"):
        print("Creating config.py from example...")
        with open("config.example.py", "r") as f:
            content = f.read()
        with open("config.py", "w") as f:
            f.write(content)
        print("✅ config.py created. Please edit it with your Discord bot token.")
    else:
        print("✅ config.py already exists")

def main():
    print("🚀 Setting up Discord Password Change Bot...\n")
    
    try:
        install_requirements()
        print()
        install_playwright()
        print()
        create_config()
        print()
        print("✅ Setup complete!")
        print("\nNext steps:")
        print("1. Edit config.py and add your Discord bot token")
        print("2. Run: python bot.py")
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
