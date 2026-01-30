#!/usr/bin/env python3
"""
HTTP server for FaceFlow project.
Serves files and handles API endpoints for landmarks, dates, and configuration.

Usage: python server.py [port]
Default port: 8080
"""

import json
import os
import platform
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
PROJECT_ROOT = Path(__file__).parent
FACE_DATA_PATH = PROJECT_ROOT / "data" / "face_data.json"
PHOTOS_DIR = PROJECT_ROOT / "photos"
REFERENCE_DIR = PROJECT_ROOT / "reference"
DATA_DIR = PROJECT_ROOT / "data"
SCAN_LOG_PATH = PROJECT_ROOT / "data" / "scan.log"
RENDER_LOG_PATH = PROJECT_ROOT / "data" / "render.log"

# Supported image extensions
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Scan state tracking
scan_state = {
    "running": False,
    "success": None,
    "return_code": None,
    "started_at": None,
    "finished_at": None
}

# Import render module
try:
    from src.render_video import (
        render_video, get_render_state, cancel_render, get_capabilities
    )
    HAS_RENDER = True
except ImportError as e:
    print(f"Warning: Could not import render module: {e}")
    HAS_RENDER = False


class FaceTimelineHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/status":
            self.handle_get_status()
        elif self.path == "/api/scan-status":
            self.handle_get_scan_status()
        elif self.path == "/api/scan-log":
            self.handle_get_scan_log()
        elif self.path.startswith("/api/open-folder"):
            self.handle_open_folder()
        elif self.path.startswith("/api/open-file"):
            self.handle_open_file()
        elif self.path == "/api/render-status":
            self.handle_get_render_status()
        elif self.path == "/api/render-log":
            self.handle_get_render_log()
        elif self.path == "/api/render-capabilities":
            self.handle_get_render_capabilities()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/save-landmarks":
            self.handle_save_landmarks()
        elif self.path == "/api/save-date":
            self.handle_save_date()
        elif self.path == "/api/save-birthdate":
            self.handle_save_birthdate()
        elif self.path == "/api/delete-photo":
            self.handle_delete_photo()
        elif self.path == "/api/scan":
            self.handle_scan()
        elif self.path == "/api/render":
            self.handle_render()
        elif self.path == "/api/render-cancel":
            self.handle_render_cancel()
        else:
            self.send_error(404, "Not Found")

    def handle_get_status(self):
        """Return status information about photos and processing."""
        try:
            # Count photos in folders
            photos_count = sum(
                1 for f in PHOTOS_DIR.glob("*")
                if f.suffix.lower() in SUPPORTED_EXTENSIONS
            ) if PHOTOS_DIR.exists() else 0

            reference_count = sum(
                1 for f in REFERENCE_DIR.glob("*")
                if f.suffix.lower() in SUPPORTED_EXTENSIONS
            ) if REFERENCE_DIR.exists() else 0

            # Load face_data.json for processed count
            processed_count = 0
            processed_filenames = set()
            subject_detected_count = 0

            if FACE_DATA_PATH.exists():
                try:
                    with open(FACE_DATA_PATH, "r") as f:
                        face_data = json.load(f)
                        for photo in face_data.get("photos", []):
                            processed_filenames.add(photo.get("filename"))
                            # Check both "subject" and legacy "ben" keys
                            faces = photo.get("faces", {})
                            subject = faces.get("subject") or faces.get("ben")
                            if subject and subject.get("detected"):
                                subject_detected_count += 1
                        processed_count = len(processed_filenames)
                except (json.JSONDecodeError, IOError):
                    pass

            # Find unprocessed photos
            unprocessed = []
            if PHOTOS_DIR.exists():
                for f in PHOTOS_DIR.glob("*"):
                    if f.suffix.lower() in SUPPORTED_EXTENSIONS and f.name not in processed_filenames:
                        unprocessed.append(f.name)

            self.send_json_response(200, {
                "photos_count": photos_count,
                "reference_count": reference_count,
                "processed_count": processed_count,
                "subject_detected_count": subject_detected_count,
                "unprocessed": unprocessed,
                "unprocessed_count": len(unprocessed)
            })
        except Exception as e:
            self.send_json_response(500, {"error": str(e)})

    def handle_open_folder(self):
        """Open a folder in the system file manager."""
        try:
            # Parse query params
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            folder_type = params.get("type", ["photos"])[0]

            # Map type to path
            folder_map = {
                "photos": PHOTOS_DIR,
                "reference": REFERENCE_DIR,
                "data": DATA_DIR,
                "out": PROJECT_ROOT / "out"
            }

            folder_path = folder_map.get(folder_type, PHOTOS_DIR)

            # Create folder if it doesn't exist
            folder_path.mkdir(parents=True, exist_ok=True)

            # Open in file manager (cross-platform)
            system = platform.system()
            if system == "Darwin":  # macOS
                subprocess.run(["open", str(folder_path)])
            elif system == "Windows":
                subprocess.run(["explorer", str(folder_path)])
            else:  # Linux
                subprocess.run(["xdg-open", str(folder_path)])

            self.send_json_response(200, {"success": True, "path": str(folder_path)})
        except Exception as e:
            self.send_json_response(500, {"error": str(e)})

    def handle_open_file(self):
        """Open a file with the default system application."""
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            file_path = params.get("path", [None])[0]

            if not file_path:
                self.send_json_response(400, {"error": "Missing path parameter"})
                return

            file_path = Path(file_path)
            if not file_path.exists():
                self.send_json_response(404, {"error": "File not found"})
                return

            # Open file with default application (cross-platform)
            system = platform.system()
            if system == "Darwin":  # macOS
                subprocess.run(["open", str(file_path)])
            elif system == "Windows":
                os.startfile(str(file_path))
            else:  # Linux
                subprocess.run(["xdg-open", str(file_path)])

            self.send_json_response(200, {"success": True, "path": str(file_path)})
        except Exception as e:
            self.send_json_response(500, {"error": str(e)})

    def handle_get_scan_status(self):
        """Return current scan status."""
        self.send_json_response(200, scan_state)

    def handle_get_scan_log(self):
        """Return current scan log contents."""
        try:
            if SCAN_LOG_PATH.exists():
                with open(SCAN_LOG_PATH, "r") as f:
                    log_content = f.read()
            else:
                log_content = ""
            self.send_json_response(200, {"log": log_content})
        except Exception as e:
            self.send_json_response(500, {"error": str(e)})

    def handle_scan(self):
        """Start face detection on photos (runs in background)."""
        global scan_state

        # Check if already running
        if scan_state["running"]:
            self.send_json_response(409, {"error": "Scan already in progress"})
            return

        detect_script = PROJECT_ROOT / "src" / "detect_faces.py"

        if not detect_script.exists():
            self.send_json_response(404, {"error": "detect_faces.py not found"})
            return

        # Reset scan state
        scan_state = {
            "running": True,
            "success": None,
            "return_code": None,
            "started_at": time.time(),
            "finished_at": None
        }

        # Clear the log file
        with open(SCAN_LOG_PATH, "w") as f:
            f.write("")

        # Start scan in background thread
        def run_scan():
            global scan_state
            try:
                # Run the script with unbuffered output
                process = subprocess.Popen(
                    [sys.executable, "-u", str(detect_script)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=str(PROJECT_ROOT),
                    bufsize=1
                )

                # Stream output to log file
                with open(SCAN_LOG_PATH, "a") as log_file:
                    for line in process.stdout:
                        log_file.write(line)
                        log_file.flush()
                        print(line, end="")  # Also print to server console

                process.wait()

                scan_state["success"] = process.returncode == 0
                scan_state["return_code"] = process.returncode

            except Exception as e:
                with open(SCAN_LOG_PATH, "a") as log_file:
                    log_file.write(f"\nError: {str(e)}\n")
                scan_state["success"] = False
                scan_state["return_code"] = -1

            finally:
                scan_state["running"] = False
                scan_state["finished_at"] = time.time()

        thread = threading.Thread(target=run_scan, daemon=True)
        thread.start()

        self.send_json_response(200, {"message": "Scan started", "status": scan_state})

    def handle_get_render_status(self):
        """Return current render status."""
        if not HAS_RENDER:
            self.send_json_response(500, {"error": "Render module not available"})
            return
        self.send_json_response(200, get_render_state())

    def handle_get_render_log(self):
        """Return current render log contents."""
        try:
            if RENDER_LOG_PATH.exists():
                with open(RENDER_LOG_PATH, "r") as f:
                    log_content = f.read()
            else:
                log_content = ""
            self.send_json_response(200, {"log": log_content})
        except Exception as e:
            self.send_json_response(500, {"error": str(e)})

    def handle_get_render_capabilities(self):
        """Return available render encoders and formats."""
        if not HAS_RENDER:
            self.send_json_response(200, {
                "has_pyav": False,
                "formats": [],
                "encoders": [],
                "error": "Render module not available"
            })
            return
        self.send_json_response(200, get_capabilities())

    def handle_render(self):
        """Start video render (runs in background)."""
        if not HAS_RENDER:
            self.send_json_response(500, {"error": "Render module not available"})
            return

        # Check if already running
        state = get_render_state()
        if state["running"]:
            self.send_json_response(409, {"error": "Render already in progress"})
            return

        try:
            content_length = int(self.headers["Content-Length"])
            body = self.rfile.read(content_length)
            config = json.loads(body)

            # Start render in background thread
            thread = threading.Thread(target=render_video, args=(config,), daemon=True)
            thread.start()

            self.send_json_response(200, {"message": "Render started"})

        except Exception as e:
            self.send_json_response(500, {"error": str(e)})

    def handle_render_cancel(self):
        """Cancel active render."""
        if not HAS_RENDER:
            self.send_json_response(500, {"error": "Render module not available"})
            return

        state = get_render_state()
        if not state["running"]:
            self.send_json_response(400, {"error": "No render in progress"})
            return

        cancel_render()
        self.send_json_response(200, {"message": "Cancel requested"})

    def handle_save_landmarks(self):
        try:
            content_length = int(self.headers["Content-Length"])
            body = self.rfile.read(content_length)
            data = json.loads(body)

            filename = data.get("filename")
            landmarks = data.get("landmarks")

            if not filename or not landmarks:
                self.send_json_response(400, {"error": "Missing filename or landmarks"})
                return

            # Load current face_data.json
            with open(FACE_DATA_PATH, "r") as f:
                face_data = json.load(f)

            # Find the photo and update landmarks
            updated = False
            for photo in face_data.get("photos", []):
                if photo.get("filename") == filename:
                    # Ensure subject face object exists
                    if "faces" not in photo:
                        photo["faces"] = {}
                    if "subject" not in photo["faces"]:
                        photo["faces"]["subject"] = {
                            "detected": True,
                            "confidence": 1.0,
                            "bounding_box": None,
                            "center": None,
                            "scale": {"face_width_px": 100, "face_height_px": 120},
                            "rotation": None,
                            "landmarks": {}
                        }

                    # Update landmarks with single-point format
                    photo["faces"]["subject"]["landmarks"] = {
                        "left_eye": [[landmarks["left_eye"]["x"], landmarks["left_eye"]["y"]]],
                        "right_eye": [[landmarks["right_eye"]["x"], landmarks["right_eye"]["y"]]],
                        "top_lip": [[landmarks["mouth"]["x"], landmarks["mouth"]["y"]]]
                    }
                    photo["faces"]["subject"]["detected"] = True

                    # Remove legacy "ben" key if present
                    if "ben" in photo["faces"]:
                        del photo["faces"]["ben"]

                    updated = True
                    print(f"Updated landmarks for {filename}")
                    break

            if not updated:
                self.send_json_response(404, {"error": f"Photo {filename} not found"})
                return

            # Save updated face_data.json
            with open(FACE_DATA_PATH, "w") as f:
                json.dump(face_data, f, indent=2)

            self.send_json_response(200, {"success": True, "filename": filename})

        except Exception as e:
            print(f"Error saving landmarks: {e}")
            self.send_json_response(500, {"error": str(e)})

    def handle_save_date(self):
        try:
            content_length = int(self.headers["Content-Length"])
            body = self.rfile.read(content_length)
            data = json.loads(body)

            filename = data.get("filename")
            date_taken = data.get("date_taken")

            if not filename or not date_taken:
                self.send_json_response(400, {"error": "Missing filename or date_taken"})
                return

            # Load current face_data.json
            with open(FACE_DATA_PATH, "r") as f:
                face_data = json.load(f)

            # Find the photo and update date
            updated = False
            for photo in face_data.get("photos", []):
                if photo.get("filename") == filename:
                    if "metadata" not in photo:
                        photo["metadata"] = {}
                    photo["metadata"]["date_taken"] = date_taken
                    photo["metadata"]["date_source"] = "manual"
                    updated = True
                    print(f"Updated date for {filename}: {date_taken}")
                    break

            if not updated:
                self.send_json_response(404, {"error": f"Photo {filename} not found"})
                return

            # Save updated face_data.json
            with open(FACE_DATA_PATH, "w") as f:
                json.dump(face_data, f, indent=2)

            self.send_json_response(200, {"success": True, "filename": filename})

        except Exception as e:
            print(f"Error saving date: {e}")
            self.send_json_response(500, {"error": str(e)})

    def handle_save_birthdate(self):
        """Save birth date to face_data.json."""
        try:
            content_length = int(self.headers["Content-Length"])
            body = self.rfile.read(content_length)
            data = json.loads(body)

            birthdate = data.get("birthDate")

            if not birthdate:
                self.send_json_response(400, {"error": "Missing birthDate"})
                return

            # Load current face_data.json
            with open(FACE_DATA_PATH, "r") as f:
                face_data = json.load(f)

            # Update birthDate
            face_data["birthDate"] = birthdate

            # Save updated face_data.json
            with open(FACE_DATA_PATH, "w") as f:
                json.dump(face_data, f, indent=2)

            print(f"Updated birthDate: {birthdate}")
            self.send_json_response(200, {"success": True, "birthDate": birthdate})

        except Exception as e:
            print(f"Error saving birthdate: {e}")
            self.send_json_response(500, {"error": str(e)})

    def handle_delete_photo(self):
        try:
            content_length = int(self.headers["Content-Length"])
            body = self.rfile.read(content_length)
            data = json.loads(body)

            filename = data.get("filename")

            if not filename:
                self.send_json_response(400, {"error": "Missing filename"})
                return

            # Load current face_data.json
            with open(FACE_DATA_PATH, "r") as f:
                face_data = json.load(f)

            # Find and remove the photo from data
            original_count = len(face_data.get("photos", []))
            face_data["photos"] = [p for p in face_data.get("photos", []) if p.get("filename") != filename]

            if len(face_data["photos"]) == original_count:
                self.send_json_response(404, {"error": f"Photo {filename} not found in data"})
                return

            # Save updated face_data.json
            with open(FACE_DATA_PATH, "w") as f:
                json.dump(face_data, f, indent=2)

            # Delete the actual photo file
            photo_path = PHOTOS_DIR / filename
            if photo_path.exists():
                os.remove(photo_path)
                print(f"Deleted photo file: {photo_path}")
            else:
                print(f"Photo file not found (already deleted?): {photo_path}")

            print(f"Removed {filename} from face_data.json")
            self.send_json_response(200, {"success": True, "filename": filename})

        except Exception as e:
            print(f"Error deleting photo: {e}")
            self.send_json_response(500, {"error": str(e)})

    def send_json_response(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


if __name__ == "__main__":
    url = f"http://localhost:{PORT}/web/"

    print(f"FaceFlow Server")
    print(f"=" * 40)
    print(f"Starting server on http://localhost:{PORT}")
    print(f"Opening {url} in your browser...")
    print(f"")
    print(f"Paths:")
    print(f"  - Photos: {PHOTOS_DIR}")
    print(f"  - Reference: {REFERENCE_DIR}")
    print(f"  - Data: {FACE_DATA_PATH}")
    print(f"")
    print("Press Ctrl+C to stop\n")

    # Open browser after a short delay to ensure server is ready
    def open_browser():
        time.sleep(0.5)
        webbrowser.open(url)

    threading.Thread(target=open_browser, daemon=True).start()

    server = HTTPServer(("", PORT), FaceTimelineHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
