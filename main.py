"""
Buildozer/python-for-android requires the app's entry point to be
literally named main.py - this file just launches phone_app.py so we
don't have to rename that file (keeping it consistent with laptop_app.py).
"""
from phone_app import JarvisPhoneApp

if __name__ == "__main__":
    JarvisPhoneApp().run()
