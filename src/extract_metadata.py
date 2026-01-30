"""Extract date metadata from photos using EXIF data or filename parsing."""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image
from PIL.ExifTags import TAGS


def get_exif_date(image_path: Path) -> Optional[datetime]:
    """Extract date from EXIF metadata."""
    try:
        with Image.open(image_path) as img:
            exif_data = img._getexif()
            if not exif_data:
                return None

            # Look for DateTimeOriginal (36867) or DateTime (306)
            for tag_id, value in exif_data.items():
                tag_name = TAGS.get(tag_id, tag_id)
                if tag_name in ('DateTimeOriginal', 'DateTime', 'DateTimeDigitized'):
                    if isinstance(value, str):
                        # Format: "2023:12:26 23:04:42"
                        try:
                            return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                        except ValueError:
                            continue
    except Exception:
        pass
    return None


def parse_filename_date(filename: str) -> Optional[datetime]:
    """Parse date from common filename patterns."""
    patterns = [
        # IMG_20231226_230442_992.jpg
        (r'IMG_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})',
         lambda m: datetime(int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]), int(m[6]))),
        # IMG-20231227-WA0024.jpg (WhatsApp)
        (r'IMG-(\d{4})(\d{2})(\d{2})-WA',
         lambda m: datetime(int(m[1]), int(m[2]), int(m[3]))),
        # PXL_20231226_230442123.jpg (Pixel)
        (r'PXL_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})',
         lambda m: datetime(int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]), int(m[6]))),
        # photo_2023-12-26_23-04-42.jpg
        (r'photo_(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})',
         lambda m: datetime(int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]), int(m[6]))),
        # 2023-12-26 or 20231226
        (r'(\d{4})-?(\d{2})-?(\d{2})',
         lambda m: datetime(int(m[1]), int(m[2]), int(m[3]))),
    ]

    for pattern, parser in patterns:
        match = re.search(pattern, filename)
        if match:
            try:
                return parser(match)
            except (ValueError, IndexError):
                continue
    return None


def extract_metadata(image_path: Path) -> dict:
    """Extract all relevant metadata from an image."""
    result = {
        "date_taken": None,
        "date_source": "unknown",
        "width": 0,
        "height": 0,
        "orientation": 1
    }

    try:
        with Image.open(image_path) as img:
            result["width"], result["height"] = img.size

            # Get orientation from EXIF
            exif_data = img._getexif()
            if exif_data:
                for tag_id, value in exif_data.items():
                    if TAGS.get(tag_id) == 'Orientation':
                        result["orientation"] = value
                        break
    except Exception:
        pass

    # Try EXIF date first
    exif_date = get_exif_date(image_path)
    if exif_date:
        result["date_taken"] = exif_date.isoformat()
        result["date_source"] = "exif"
        return result

    # Fall back to filename parsing
    filename_date = parse_filename_date(image_path.name)
    if filename_date:
        result["date_taken"] = filename_date.isoformat()
        result["date_source"] = "filename"
        return result

    return result


if __name__ == "__main__":
    # Test with a sample file
    import sys
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        print(extract_metadata(path))
