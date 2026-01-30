#!/usr/bin/env python3
"""
Face detection and recognition script for FaceFlow project.

Detects all faces in photos, identifies the subject using reference photos,
and outputs structured JSON with position, scale, and rotation data.
"""

import json
import sys
from pathlib import Path
from typing import List, Optional

import face_recognition
import numpy as np
from PIL import Image

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from extract_metadata import extract_metadata
from extract_rotation import calculate_rotation


# Paths
PROJECT_ROOT = Path(__file__).parent.parent
PHOTOS_DIR = PROJECT_ROOT / "photos"
REFERENCE_DIR = PROJECT_ROOT / "reference"
DATA_FILE = PROJECT_ROOT / "data" / "face_data.json"

# Configuration
FACE_DETECTION_MODEL = "hog"  # "hog" is faster, "cnn" is more accurate
RECOGNITION_TOLERANCE = 0.6  # Lower = stricter matching (default 0.6)
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def load_reference_encodings() -> List[np.ndarray]:
    """Load face encodings from reference photos of the subject."""
    encodings = []
    reference_files = list(REFERENCE_DIR.glob("*"))
    reference_files = [f for f in reference_files if f.suffix.lower() in SUPPORTED_EXTENSIONS]

    if not reference_files:
        print(f"Warning: No reference photos found in {REFERENCE_DIR}")
        print("Please add 1-3 clear photos of the subject to the reference/ folder")
        return encodings

    print(f"Loading {len(reference_files)} reference photo(s)...")

    for ref_path in reference_files:
        try:
            image = face_recognition.load_image_file(str(ref_path))
            face_encodings = face_recognition.face_encodings(image)
            if face_encodings:
                encodings.append(face_encodings[0])
                print(f"  - Loaded encoding from {ref_path.name}")
            else:
                print(f"  - Warning: No face found in {ref_path.name}")
        except Exception as e:
            print(f"  - Error loading {ref_path.name}: {e}")

    return encodings


def get_subject_confidence(face_encoding: np.ndarray, reference_encodings: List[np.ndarray]) -> float:
    """Calculate confidence that a face is the subject based on reference encodings."""
    if not reference_encodings:
        return 0.0

    # Calculate distances to all reference encodings
    distances = face_recognition.face_distance(reference_encodings, face_encoding)

    # Convert distance to confidence (0-1 scale)
    # Distance of 0 = perfect match (confidence 1.0)
    # Distance of 0.6 = threshold (confidence ~0.5)
    # Distance of 1.0+ = no match (confidence ~0)
    min_distance = min(distances)
    confidence = max(0, 1 - (min_distance / RECOGNITION_TOLERANCE) * 0.5)

    return round(confidence, 3)


def process_photo(
    photo_path: Path,
    reference_encodings: List[np.ndarray]
) -> dict:
    """Process a single photo and extract face data."""
    result = {
        "filename": photo_path.name,
        "metadata": extract_metadata(photo_path),
        "faces": {
            "total_count": 0,
            "subject": {
                "detected": False,
                "confidence": 0.0,
                "bounding_box": None,
                "center": None,
                "scale": None,
                "rotation": None,
                "landmarks": None
            },
            "others": []
        },
        "processing_error": None
    }

    try:
        # Load image
        image = face_recognition.load_image_file(str(photo_path))
        height, width = image.shape[:2]

        # Update metadata with actual dimensions (in case EXIF was wrong)
        result["metadata"]["width"] = width
        result["metadata"]["height"] = height

        # Detect faces
        face_locations = face_recognition.face_locations(image, model=FACE_DETECTION_MODEL)
        face_encodings = face_recognition.face_encodings(image, face_locations)
        face_landmarks = face_recognition.face_landmarks(image, face_locations)

        result["faces"]["total_count"] = len(face_locations)

        if not face_locations:
            return result

        # Find subject among detected faces
        subject_index = -1
        subject_confidence = 0.0

        if reference_encodings:
            for i, encoding in enumerate(face_encodings):
                confidence = get_subject_confidence(encoding, reference_encodings)
                if confidence > subject_confidence and confidence > 0.4:  # Minimum threshold
                    subject_confidence = confidence
                    subject_index = i

        # Process each face
        for i, (location, landmarks) in enumerate(zip(face_locations, face_landmarks)):
            top, right, bottom, left = location

            # Create bounding box
            bbox = {
                "x": left,
                "y": top,
                "width": right - left,
                "height": bottom - top
            }

            # Calculate center
            center = {
                "x": (left + right) // 2,
                "y": (top + bottom) // 2
            }

            # Calculate scale
            face_width = right - left
            scale = {
                "relative_width": round(face_width / width, 4),
                "relative_height": round((bottom - top) / height, 4),
                "face_width_px": face_width,
                "face_height_px": bottom - top
            }

            # Calculate rotation
            rotation = calculate_rotation(landmarks, width, height)

            if i == subject_index:
                # This is the subject
                result["faces"]["subject"] = {
                    "detected": True,
                    "confidence": subject_confidence,
                    "bounding_box": bbox,
                    "center": center,
                    "scale": scale,
                    "rotation": rotation,
                    "landmarks": landmarks
                }
            else:
                # Other person
                result["faces"]["others"].append({
                    "id": len(result["faces"]["others"]) + 1,
                    "bounding_box": bbox,
                    "center": center,
                    "scale": scale,
                    "rotation": rotation
                })

    except Exception as e:
        result["processing_error"] = str(e)

    return result


def load_existing_data() -> dict:
    """Load existing face_data.json if it exists."""
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load existing data: {e}")
    return None


def migrate_face_data(data: dict) -> dict:
    """Migrate old 'ben' key to 'subject' for backwards compatibility."""
    if not data or "photos" not in data:
        return data

    for photo in data["photos"]:
        if "faces" in photo:
            # Migrate "ben" to "subject" if needed
            if "ben" in photo["faces"] and "subject" not in photo["faces"]:
                photo["faces"]["subject"] = photo["faces"]["ben"]
                del photo["faces"]["ben"]

    return data


def main():
    """Main entry point."""
    from datetime import datetime

    print("=" * 60)
    print("FaceFlow - Face Detection")
    print("=" * 60)

    # Load existing data to skip already processed photos
    existing_data = load_existing_data()
    existing_data = migrate_face_data(existing_data)
    existing_photos = {}
    existing_birthdate = None
    if existing_data:
        for photo in existing_data.get("photos", []):
            existing_photos[photo.get("filename")] = photo
        existing_birthdate = existing_data.get("birthDate")
        print(f"\nLoaded existing data with {len(existing_photos)} photos")

    # Load reference encodings
    reference_encodings = load_reference_encodings()
    if not reference_encodings:
        print("\nNo reference photos found. Will detect faces but cannot identify subject.")
        print("Add photos to reference/ folder and run again.\n")

    # Get all photos
    photo_files = []
    for ext in SUPPORTED_EXTENSIONS:
        photo_files.extend(PHOTOS_DIR.glob(f"*{ext}"))
        photo_files.extend(PHOTOS_DIR.glob(f"*{ext.upper()}"))

    photo_files = sorted(set(photo_files))
    photo_filenames = {p.name for p in photo_files}
    print(f"Found {len(photo_files)} photos in folder")

    if not photo_files:
        print(f"No photos found in {PHOTOS_DIR}")
        return

    # Remove deleted photos from existing data
    deleted_photos = [name for name in existing_photos if name not in photo_filenames]
    if deleted_photos:
        print(f"Removing {len(deleted_photos)} deleted photo(s) from database")
        for name in deleted_photos:
            del existing_photos[name]

    # Filter to only new photos
    new_photos = [p for p in photo_files if p.name not in existing_photos]
    skipped_count = len(photo_files) - len(new_photos)

    if skipped_count > 0:
        print(f"Skipping {skipped_count} already processed photos")

    # Start with existing photos (preserves manual edits)
    all_photos = list(existing_photos.values())

    if not new_photos and not deleted_photos:
        print("\nNo changes. All photos already analyzed.")
        return

    if new_photos:
        print(f"Processing {len(new_photos)} new photo(s)\n")
    new_processed = 0

    for i, photo_path in enumerate(new_photos, 1):
        print(f"[{i}/{len(new_photos)}] Processing {photo_path.name}...", end=" ")
        try:
            photo_data = process_photo(photo_path, reference_encodings)

            # Convert landmarks to serializable format (tuples to lists)
            if photo_data["faces"]["subject"]["landmarks"]:
                landmarks = photo_data["faces"]["subject"]["landmarks"]
                photo_data["faces"]["subject"]["landmarks"] = {
                    k: [list(p) for p in v] for k, v in landmarks.items()
                }

            all_photos.append(photo_data)
            new_processed += 1

            # Status indicator
            if photo_data["processing_error"]:
                print("ERROR")
            elif photo_data["faces"]["subject"]["detected"]:
                conf = photo_data["faces"]["subject"]["confidence"]
                print(f"Subject found (confidence: {conf:.2f})")
            elif photo_data["faces"]["total_count"] > 0:
                print(f"{photo_data['faces']['total_count']} face(s), subject not identified")
            else:
                print("No faces detected")

        except Exception as e:
            print(f"FAILED: {e}")
            all_photos.append({
                "filename": photo_path.name,
                "processing_error": str(e)
            })

    # Build final results - preserve existing birthDate if present
    results = {
        "version": "1.0.0",
        "birthDate": existing_birthdate or "2000-01-01",
        "generated_at": datetime.now().isoformat(),
        "reference_photos_count": len(reference_encodings),
        "photos": all_photos
    }

    # Write output
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nOutput written to: {DATA_FILE}")

    # Summary
    subject_count = sum(1 for p in results["photos"]
                    if p.get("faces", {}).get("subject", {}).get("detected", False))
    error_count = sum(1 for p in results["photos"]
                      if p.get("processing_error"))

    print(f"\nSummary:")
    print(f"  - Total photos in database: {len(results['photos'])}")
    print(f"  - New photos processed: {new_processed}")
    print(f"  - Existing photos preserved: {skipped_count}")
    print(f"  - Deleted photos removed: {len(deleted_photos)}")
    print(f"  - Subject identified in: {subject_count} photos")
    print(f"  - Processing errors: {error_count}")


if __name__ == "__main__":
    main()
