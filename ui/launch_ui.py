#!/usr/bin/env python3
"""
Launch the Cadence UI Visualizer

Usage:
    python launch_ui.py [results_directory]
"""

import sys
import subprocess


def install_flask():
    """Install Flask if not available"""
    try:
        import flask

        print("Flask Version:", flask.__version__)
        print("✓ Flask is available")
    except ImportError:
        print("Installing Flask...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "flask"])
        print("✓ Flask installed successfully")


def main():
    print("🧬 Cadence Evolution Visualizer")
    print("=" * 40)

    # Install dependencies
    install_flask()

    # Set up path
    # ui_dir = r"cadence\ui"
    # cadence_dir = "cadence"

    # Change to UI directory and add cadence to path
    # os.chdir(ui_dir)
    # sys.path.insert(0, cadence_dir)

    # Launch the Flask app
    print("\n🚀 Starting visualization server...")
    print("📊 Open your browser to: http://localhost:5000")
    print("⏹️  Press Ctrl+C to stop the server")
    print("-" * 40)

    try:
        # Import and run the app
        from app import app

        app.run(debug=True, host="0.0.0.0", port=5000)
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        sys.exit(1)
        sys.exit(1)


if __name__ == "__main__":
    main()
