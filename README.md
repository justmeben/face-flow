# FaceFlow

Local web UI tool to create a video of your face-over-time, with photos automatically aligned and age displayed.

## Quick Start

1. **Setup**
   ```bash
   python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Run**
   ```bash
   python server.py
   # Open http://localhost:8080/web/
   ```

1. **Add Photos**
   - Put your face photos in `photos/`
   - Put 1-3 clear reference photos in `reference/`


4. **Scan** - Click "Scan Photos" on the Home page to detect faces

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
