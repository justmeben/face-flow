# FaceFlow

Create a video showing how a face changes over time, with photos automatically aligned and age displayed.

## Quick Start

1. **Setup**
   ```bash
   python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Add Photos**
   - Put photos in `photos/`
   - Put 1-3 clear reference photos in `reference/`

3. **Run**
   ```bash
   python server.py
   # Open http://localhost:8080/web/
   ```

4. **Scan** - Click "Scan Photos" on the Status page to detect faces

## Pages

- **Preview** - View photos with face centered, scrub through timeline, edit landmarks, debug detection
- **Status** - See processing stats, run face detection
- **Render** - Export video (coming soon)

## Controls

All controls are in the left sidebar:

| Control | Description |
|---------|-------------|
| Birth Date | Set subject's birth date for age calculation (saved to data/face_data.json) |
| Face Width | Size of face in preview (50-300px) |
| Scale/Rotate | Enable face normalization transforms |
| Show Age | Display calculated age overlay |
| Slideshow | Auto-advance through photos |
| Debug Mode | Show bounding boxes, landmarks, and edit age |
| Fix Detection | Manually set face landmarks for photos where auto-detection failed |
| Delete Photo | Remove current photo from disk and database |

## Requirements

- Python 3.8+

## Project Structure

```
faceflow/
├── photos/              # Your photos to analyze
├── reference/           # 1-3 clear reference photos
├── data/
│   └── face_data.json   # Detection results + birth date
├── src/
│   └── detect_faces.py  # Face detection script
├── web/
│   └── index.html       # Web viewer
├── video/               # Remotion video project
├── server.py            # HTTP server with API
└── requirements.txt
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `←` `→` | Navigate photos |
| `1` `2` `3` | Select landmark (in edit mode) |
| `Esc` | Cancel landmark editing |
| Mouse wheel | Adjust scale (preview) |
