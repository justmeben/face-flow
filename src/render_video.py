#!/usr/bin/env python3
"""
Video rendering for FaceFlow.
Exports face timeline as video with consistent face transformations.
"""

import json
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Try to import PyAV for high-quality encoding
try:
    import av
    HAS_PYAV = True
except ImportError:
    HAS_PYAV = False

PROJECT_ROOT = Path(__file__).parent.parent
PHOTOS_DIR = PROJECT_ROOT / "photos"
FACE_DATA_PATH = PROJECT_ROOT / "data" / "face_data.json"
RENDER_LOG_PATH = PROJECT_ROOT / "data" / "render.log"


# Render state for progress tracking
render_state = {
    "running": False,
    "progress": 0,
    "current_frame": 0,
    "total_frames": 0,
    "status": "idle",
    "error": None,
    "output_path": None,
    "overlay_path": None,
    "age_mode": None,
    "started_at": None,
    "finished_at": None,
    "cancelled": False
}


def log(message):
    """Write to render log file."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {message}\n"
    with open(RENDER_LOG_PATH, "a") as f:
        f.write(line)
    print(line, end="")


def get_capabilities():
    """Return available encoders and formats."""
    capabilities = {
        "has_pyav": HAS_PYAV,
        "formats": ["mp4", "gif", "png_sequence"],
        "encoders": []
    }

    if HAS_PYAV:
        capabilities["encoders"].append("h264 (PyAV)")

    # OpenCV is always available as fallback
    capabilities["encoders"].append("opencv (fallback)")

    return capabilities


def get_subject_data(photo):
    """Get subject face data from photo, handling legacy 'ben' key."""
    faces = photo.get("faces", {})
    return faces.get("subject") or faces.get("ben")


def get_face_points(landmarks):
    """Get face anchor points from landmarks."""
    if not landmarks:
        return None

    left_eye = landmarks.get("left_eye")
    right_eye = landmarks.get("right_eye")
    top_lip = landmarks.get("top_lip")

    if not left_eye or not right_eye or not top_lip:
        return None

    def avg(points):
        x = sum(p[0] for p in points) / len(points)
        y = sum(p[1] for p in points) / len(points)
        return {"x": x, "y": y}

    return {
        "leftEye": avg(left_eye),
        "rightEye": avg(right_eye),
        "mouth": avg(top_lip)
    }


def calculate_age(photo_date, birth_date):
    """Calculate age in years from photo date and birth date."""
    if not photo_date or not birth_date:
        return None

    try:
        photo_dt = datetime.fromisoformat(photo_date.replace("Z", "+00:00"))
        birth_dt = datetime.fromisoformat(birth_date)

        diff = photo_dt - birth_dt
        years = diff.total_seconds() / (365.25 * 24 * 60 * 60)
        return years
    except (ValueError, TypeError):
        return None


def compute_similarity_transform(src_points, viewport_width, viewport_height,
                                  target_face_width, do_scale, do_rotate, angle_offset):
    """
    Compute 2x3 affine transform matrix.
    Same math as preview.js computeSimilarityTransform().

    Returns a 2x3 matrix for cv2.warpAffine.
    """
    cx = viewport_width / 2
    cy = viewport_height / 2

    # Convert angle offset from degrees to radians
    angle_offset_rad = angle_offset * math.pi / 180

    # Calculate eye distance and angle
    src_dx = src_points["rightEye"]["x"] - src_points["leftEye"]["x"]
    src_dy = src_points["rightEye"]["y"] - src_points["leftEye"]["y"]
    src_dist = math.sqrt(src_dx * src_dx + src_dy * src_dy)
    src_angle = math.atan2(src_dy, src_dx)

    # Compute scale and rotation
    scale = target_face_width / src_dist if do_scale else 1.0
    rotation = angle_offset_rad - src_angle if do_rotate else angle_offset_rad

    # Build transform components
    cos_r = math.cos(rotation) * scale
    sin_r = math.sin(rotation) * scale

    # Source midpoint (between eyes)
    src_mid_x = (src_points["leftEye"]["x"] + src_points["rightEye"]["x"]) / 2
    src_mid_y = (src_points["leftEye"]["y"] + src_points["rightEye"]["y"]) / 2

    # Translation to center
    tx = cx - (cos_r * src_mid_x - sin_r * src_mid_y)
    ty = cy - (sin_r * src_mid_x + cos_r * src_mid_y)

    # Return 2x3 matrix for cv2.warpAffine
    return np.array([
        [cos_r, -sin_r, tx],
        [sin_r, cos_r, ty]
    ], dtype=np.float32)


def get_age_font(width, height):
    """Get the font for age overlay."""
    font_size = int(min(width, height) * 0.08)  # 8% of smaller dimension
    try:
        font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNSDisplay.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "C:/Windows/Fonts/arial.ttf"
        ]
        for path in font_paths:
            if os.path.exists(path):
                return ImageFont.truetype(path, font_size)
        return ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()


def render_age_overlay(frame, age, width, height):
    """
    Render age text overlay on frame using Pillow.
    Returns frame with age overlay.
    """
    if age is None:
        return frame

    # Convert BGR to RGB for Pillow
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(frame_rgb)
    draw = ImageDraw.Draw(pil_image)

    age_text = f"{age:.2f}"
    font = get_age_font(width, height)

    # Get text bounding box
    bbox = draw.textbbox((0, 0), age_text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Position in top-right with padding
    padding = 20
    x = width - text_width - padding
    y = padding

    # Draw shadow
    shadow_offset = 3
    draw.text((x + shadow_offset, y + shadow_offset), age_text,
              font=font, fill=(0, 0, 0, 180))

    # Draw text
    draw.text((x, y), age_text, font=font, fill=(255, 255, 255))

    # Convert back to BGR for OpenCV
    result = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    return result


def render_age_overlay_greenscreen(age, width, height):
    """
    Render age text on bright green background for chroma keying.
    Returns BGR numpy array.
    """
    # Create bright green background (0, 255, 0 in RGB, or 0, 255, 0 in BGR)
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :] = (0, 255, 0)  # BGR green

    if age is None:
        return frame

    # Convert to PIL for text rendering
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(frame_rgb)
    draw = ImageDraw.Draw(pil_image)

    age_text = f"{age:.2f}"
    font = get_age_font(width, height)

    # Get text bounding box
    bbox = draw.textbbox((0, 0), age_text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Position in top-right with padding
    padding = 20
    x = width - text_width - padding
    y = padding

    # Draw shadow (dark gray, not black to avoid keying issues)
    shadow_offset = 3
    draw.text((x + shadow_offset, y + shadow_offset), age_text,
              font=font, fill=(40, 40, 40))

    # Draw text (white)
    draw.text((x, y), age_text, font=font, fill=(255, 255, 255))

    # Convert back to BGR
    return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)


def render_video(config):
    """
    Main render function. Runs in background thread.

    Config dict:
    - output_folder: str (relative to project root)
    - filename: str (without extension)
    - format: "mp4" | "gif" | "png_sequence"
    - width: int
    - height: int
    - frame_duration_ms: int (ms per photo, FPS fixed at 30)
    - target_face_width: int
    - angle_offset: float (degrees)
    - do_scale: bool
    - do_rotate: bool
    - age_mode: "show" | "hide" | "separate" | "overlay_only"
    - start_frame: int (1-indexed)
    - end_frame: int (1-indexed)
    - birth_date: str
    - blur_amount: int (0 = no blur, higher = more blur)
    """
    global render_state

    try:
        render_state["running"] = True
        render_state["progress"] = 0
        render_state["current_frame"] = 0
        render_state["status"] = "initializing"
        render_state["error"] = None
        render_state["output_path"] = None
        render_state["overlay_path"] = None
        render_state["age_mode"] = None
        render_state["cancelled"] = False
        render_state["started_at"] = time.time()

        # Clear log
        with open(RENDER_LOG_PATH, "w") as f:
            f.write("")

        age_mode = config.get("age_mode", "show")
        # Support legacy show_age boolean
        if "show_age" in config and "age_mode" not in config:
            age_mode = "show" if config["show_age"] else "hide"

        blur_amount = config.get("blur_amount", 0)

        log("Starting render...")
        log(f"Format: {config['format']}")
        log(f"Resolution: {config['width']}x{config['height']}")
        log(f"Frame duration: {config['frame_duration_ms']}ms per photo")
        log(f"Age mode: {age_mode}")
        if blur_amount > 0:
            log(f"Blur: {blur_amount}px")

        # Load face data
        if not FACE_DATA_PATH.exists():
            raise FileNotFoundError("face_data.json not found")

        with open(FACE_DATA_PATH, "r") as f:
            face_data = json.load(f)

        birth_date = config.get("birth_date") or face_data.get("birthDate", "1996-02-07")
        photos = face_data.get("photos", [])

        # Filter photos with subject detected
        valid_photos = []
        for photo in photos:
            subject = get_subject_data(photo)
            if subject and subject.get("detected"):
                valid_photos.append(photo)

        # Sort by date
        valid_photos.sort(key=lambda p: p.get("metadata", {}).get("date_taken", ""))

        log(f"Found {len(valid_photos)} photos with subject detected")

        # Apply frame range (1-indexed to 0-indexed)
        start_idx = max(0, config.get("start_frame", 1) - 1)
        end_idx = min(len(valid_photos), config.get("end_frame", len(valid_photos)))
        valid_photos = valid_photos[start_idx:end_idx]

        if not valid_photos:
            raise ValueError("No photos to render in selected range")

        log(f"Rendering frames {start_idx + 1} to {end_idx} ({len(valid_photos)} photos)")

        # Calculate total output frames (30 FPS, frame_duration_ms per photo)
        fps = 30
        frames_per_photo = max(1, int(config["frame_duration_ms"] * fps / 1000))
        total_output_frames = len(valid_photos) * frames_per_photo

        render_state["total_frames"] = len(valid_photos)
        log(f"Output: {total_output_frames} frames at {fps} FPS ({frames_per_photo} frames per photo)")

        # Setup output path
        output_folder = PROJECT_ROOT / config.get("output_folder", "out")
        output_folder.mkdir(parents=True, exist_ok=True)

        output_format = config.get("format", "mp4")
        filename = config.get("filename", "faceflow_render")

        width = config["width"]
        height = config["height"]

        # Initialize writer based on format (skip for overlay_only mode)
        writer = None
        output_path = None
        gif_frames = []

        if age_mode == "overlay_only":
            # No video output, only overlay PNGs
            output_path = str(output_folder / f"{filename}_overlay")
            log(f"Overlay-only mode: {output_path}")
        elif output_format == "png_sequence":
            # Create subfolder for images
            seq_folder = output_folder / filename
            seq_folder.mkdir(parents=True, exist_ok=True)
            output_path = str(seq_folder)
            log(f"Output folder: {output_path}")
        elif output_format == "gif":
            output_path = str(output_folder / f"{filename}.gif")
            writer = "gif"
            log(f"Output file: {output_path}")
        else:  # mp4
            output_path = str(output_folder / f"{filename}.mp4")
            if HAS_PYAV:
                writer = "pyav"
                container = av.open(output_path, mode='w')
                stream = container.add_stream('h264', rate=fps)
                stream.width = width
                stream.height = height
                stream.pix_fmt = 'yuv420p'
                # Set encoding options for quality
                stream.options = {'crf': '18'}
                log(f"Using PyAV H.264 encoder")
            else:
                writer = "opencv"
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                video_writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
                log(f"Using OpenCV fallback encoder")
            log(f"Output file: {output_path}")

        render_state["output_path"] = output_path
        render_state["age_mode"] = age_mode
        render_state["status"] = "rendering"

        # Setup overlay video writer for 'separate' and 'overlay_only' modes
        overlay_path = None
        overlay_writer = None
        overlay_container = None
        overlay_stream = None

        if age_mode in ("separate", "overlay_only"):
            overlay_path = str(output_folder / f"{filename}_overlay.mp4")
            if HAS_PYAV:
                overlay_container = av.open(overlay_path, mode='w')
                overlay_stream = overlay_container.add_stream('h264', rate=fps)
                overlay_stream.width = width
                overlay_stream.height = height
                overlay_stream.pix_fmt = 'yuv420p'
                overlay_stream.options = {'crf': '18'}
                overlay_writer = "pyav"
            else:
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                overlay_writer = cv2.VideoWriter(overlay_path, fourcc, fps, (width, height))
            log(f"Overlay video (greenscreen): {overlay_path}")

        # Process each photo
        for i, photo in enumerate(valid_photos):
            if render_state["cancelled"]:
                log("Render cancelled by user")
                render_state["status"] = "cancelled"
                break

            render_state["current_frame"] = i + 1
            render_state["progress"] = int((i / len(valid_photos)) * 100)

            filename_photo = photo.get("filename")
            photo_path = PHOTOS_DIR / filename_photo

            if not photo_path.exists():
                log(f"Warning: Photo not found: {filename_photo}")
                continue

            # Load image
            img = cv2.imread(str(photo_path))
            if img is None:
                log(f"Warning: Could not load: {filename_photo}")
                continue

            # Get face points
            subject = get_subject_data(photo)
            landmarks = subject.get("landmarks") if subject else None
            face_points = get_face_points(landmarks)

            if not face_points:
                log(f"Warning: No landmarks for: {filename_photo}")
                continue

            # Compute transform
            transform_matrix = compute_similarity_transform(
                face_points,
                width, height,
                config.get("target_face_width", 150),
                config.get("do_scale", True),
                config.get("do_rotate", True),
                config.get("angle_offset", 0)
            )

            # Apply transform
            frame = cv2.warpAffine(img, transform_matrix, (width, height),
                                   borderMode=cv2.BORDER_CONSTANT,
                                   borderValue=(0, 0, 0))

            # Apply blur if requested
            if blur_amount > 0:
                # Kernel size must be odd
                kernel_size = blur_amount * 2 + 1
                frame = cv2.GaussianBlur(frame, (kernel_size, kernel_size), 0)

            # Get age for this photo
            photo_date = photo.get("metadata", {}).get("date_taken")
            age = calculate_age(photo_date, birth_date)

            # Handle age overlay based on mode
            if age_mode == "show":
                frame = render_age_overlay(frame, age, width, height)
            elif age_mode == "separate":
                # Write greenscreen overlay frame to separate video
                overlay_frame = render_age_overlay_greenscreen(age, width, height)
                for _ in range(frames_per_photo):
                    if overlay_writer == "pyav":
                        overlay_rgb = cv2.cvtColor(overlay_frame, cv2.COLOR_BGR2RGB)
                        av_frame = av.VideoFrame.from_ndarray(overlay_rgb, format='rgb24')
                        for packet in overlay_stream.encode(av_frame):
                            overlay_container.mux(packet)
                    else:
                        overlay_writer.write(overlay_frame)
            elif age_mode == "overlay_only":
                # Only write the greenscreen overlay, skip main video frame
                overlay_frame = render_age_overlay_greenscreen(age, width, height)
                for _ in range(frames_per_photo):
                    if overlay_writer == "pyav":
                        overlay_rgb = cv2.cvtColor(overlay_frame, cv2.COLOR_BGR2RGB)
                        av_frame = av.VideoFrame.from_ndarray(overlay_rgb, format='rgb24')
                        for packet in overlay_stream.encode(av_frame):
                            overlay_container.mux(packet)
                    else:
                        overlay_writer.write(overlay_frame)
                if (i + 1) % 10 == 0:
                    log(f"Processed {i + 1}/{len(valid_photos)} photos")
                continue  # Skip writing the main video frame
            # 'hide' mode: don't add overlay, just use frame as-is

            # Write frame(s)
            if output_format == "png_sequence":
                frame_path = Path(output_path) / f"frame_{i+1:04d}.png"
                cv2.imwrite(str(frame_path), frame)
            elif output_format == "gif":
                # Convert BGR to RGB and store for GIF
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_frame = Image.fromarray(frame_rgb)
                # For GIF, only add one frame per photo (no duplication)
                gif_frames.append(pil_frame)
            else:  # mp4
                # Write multiple frames for smooth playback
                for _ in range(frames_per_photo):
                    if writer == "pyav":
                        # Convert BGR to RGB
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        av_frame = av.VideoFrame.from_ndarray(frame_rgb, format='rgb24')
                        for packet in stream.encode(av_frame):
                            container.mux(packet)
                    else:
                        video_writer.write(frame)

            if (i + 1) % 10 == 0:
                log(f"Processed {i + 1}/{len(valid_photos)} photos")

        # Finalize output
        if not render_state["cancelled"]:
            log("Finalizing output...")

            # Finalize overlay video if used
            if age_mode in ("separate", "overlay_only") and overlay_writer:
                if overlay_writer == "pyav":
                    for packet in overlay_stream.encode():
                        overlay_container.mux(packet)
                    overlay_container.close()
                else:
                    overlay_writer.release()
                log(f"Overlay video saved: {overlay_path}")
                render_state["overlay_path"] = overlay_path

            if age_mode == "overlay_only":
                # Only overlay was rendered
                render_state["output_path"] = overlay_path
            else:
                if output_format == "gif" and gif_frames:
                    # Save GIF using Pillow
                    gif_frames[0].save(
                        output_path,
                        save_all=True,
                        append_images=gif_frames[1:],
                        duration=config["frame_duration_ms"],
                        loop=0,
                        optimize=True
                    )
                    log(f"GIF saved: {len(gif_frames)} frames")
                elif output_format == "mp4":
                    if writer == "pyav":
                        # Flush encoder
                        for packet in stream.encode():
                            container.mux(packet)
                        container.close()
                    else:
                        video_writer.release()

                log(f"Video saved: {output_path}")

            render_state["progress"] = 100
            render_state["status"] = "complete"
            log("Render complete!")

    except Exception as e:
        log(f"Error: {str(e)}")
        render_state["status"] = "error"
        render_state["error"] = str(e)

    finally:
        render_state["running"] = False
        render_state["finished_at"] = time.time()


def cancel_render():
    """Cancel the current render."""
    global render_state
    render_state["cancelled"] = True
    log("Cancellation requested...")


def get_render_state():
    """Return current render state."""
    return render_state.copy()


if __name__ == "__main__":
    # Test render with defaults
    print("Capabilities:", get_capabilities())

    config = {
        "output_folder": "out",
        "filename": "test_render",
        "format": "mp4",
        "width": 1920,
        "height": 1080,
        "frame_duration_ms": 200,
        "target_face_width": 150,
        "angle_offset": 0,
        "do_scale": True,
        "do_rotate": True,
        "show_age": True,
        "start_frame": 1,
        "end_frame": 10,
        "birth_date": "1996-02-07"
    }

    render_video(config)
