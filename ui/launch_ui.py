import sys


def main():
    print("Cadence Evolution Visualizer")
    print("-" * 40)

    # Launch the Flask app
    print("\n Starting visualization server...")
    print("Open your browser to: http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    print("-" * 40)

    try:
        from app import app

        app.run(debug=True, host="0.0.0.0", port=5000)
    except KeyboardInterrupt:
        print("Server stopped by user")
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
