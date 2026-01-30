# Face Normalization System

This document describes the JSON data structure and normalization algorithm used to align faces across multiple photos so that facial features (eyes, mouth) appear at consistent screen positions.

## Overview

The system detects faces in photos, extracts facial landmarks, and applies a **similarity transformation** (scale + rotation + translation) to normalize each photo so that:

- The eyes are horizontally aligned
- The eye spacing is consistent across all photos
- The face is centered on screen
- No skew/shear distortion is applied

---

## JSON Data Structure

### Main File: `data/face_data.json`

```json
{
  "version": "1.0.0",
  "generated_at": "2024-01-27T15:30:00.000Z",
  "reference_photos_count": 3,
  "photos": [
    { /* photo object */ },
    { /* photo object */ },
    ...
  ]
}
```

### Photo Object

```json
{
  "filename": "IMG_20231226_230442_992.jpg",
  "metadata": {
    "date_taken": "2023-12-26T23:04:42",
    "date_source": "exif",        // "exif" | "filename" | "unknown"
    "width": 3024,
    "height": 4032,
    "orientation": 1
  },
  "faces": {
    "total_count": 3,
    "subject": {
      "detected": true,
      "confidence": 0.92,
      "bounding_box": {
        "x": 450,
        "y": 320,
        "width": 180,
        "height": 220
      },
      "center": {
        "x": 540,
        "y": 430
      },
      "scale": {
        "relative_width": 0.059,
        "relative_height": 0.055,
        "face_width_px": 180,
        "face_height_px": 220
      },
      "rotation": {
        "roll": -5.2,
        "yaw": 12.3,
        "pitch": -3.1
      },
      "landmarks": {
        "left_eye": [[x, y], [x, y], ...],    // 6 points
        "right_eye": [[x, y], [x, y], ...],   // 6 points
        "nose_bridge": [[x, y], ...],
        "nose_tip": [[x, y], ...],
        "top_lip": [[x, y], ...],             // 12 points
        "bottom_lip": [[x, y], ...],
        "chin": [[x, y], ...]
      }
    },
    "others": [
      {
        "id": 1,
        "bounding_box": { "x": 100, "y": 200, "width": 150, "height": 180 },
        "center": { "x": 175, "y": 290 },
        "scale": { ... },
        "rotation": { ... }
      }
    ]
  },
  "processing_error": null
}
```

### Key Landmarks for Normalization

For normalization, we use **3 anchor points** derived from the landmarks:

| Point | Source | Calculation |
|-------|--------|-------------|
| **Left Eye Center** | `landmarks.left_eye` | Average of all 6 eye corner points |
| **Right Eye Center** | `landmarks.right_eye` | Average of all 6 eye corner points |
| **Mouth Center** | `landmarks.top_lip` | Average of all 12 lip points |

---

## Manual Landmark Editing

For photos where automatic detection fails or is inaccurate, use the **Landmark Editor**:

1. Start the server: `python server.py`
2. Open `http://localhost:8080/web/`
3. Navigate to the photo in Preview mode
4. Click "Fix Detection" in the Tools section
5. Click to place: Left Eye → Right Eye → Mouth
6. Click "Save"

The editor directly updates `data/face_data.json` with your manually placed landmarks.

---

## Normalization Algorithm

### Step 1: Extract Source Points

From the landmarks, calculate the center of each feature:

```javascript
function getFacePoints(landmarks) {
    // Center of left eye (average of all eye points)
    const leftEyeCenter = {
        x: landmarks.left_eye.reduce((sum, p) => sum + p[0], 0) / landmarks.left_eye.length,
        y: landmarks.left_eye.reduce((sum, p) => sum + p[1], 0) / landmarks.left_eye.length
    };

    // Center of right eye
    const rightEyeCenter = {
        x: landmarks.right_eye.reduce((sum, p) => sum + p[0], 0) / landmarks.right_eye.length,
        y: landmarks.right_eye.reduce((sum, p) => sum + p[1], 0) / landmarks.right_eye.length
    };

    // Center of mouth
    const mouthCenter = {
        x: landmarks.top_lip.reduce((sum, p) => sum + p[0], 0) / landmarks.top_lip.length,
        y: landmarks.top_lip.reduce((sum, p) => sum + p[1], 0) / landmarks.top_lip.length
    };

    return { leftEye: leftEyeCenter, rightEye: rightEyeCenter, mouth: mouthCenter };
}
```

### Step 2: Compute Similarity Transform

The similarity transform aligns faces using **only scale, rotation, and translation** (no skew):

```javascript
function computeSimilarityTransform(srcPoints, viewportWidth, viewportHeight, targetEyeDistance) {
    // Viewport center (where face will be centered)
    const cx = viewportWidth / 2;
    const cy = viewportHeight / 2;

    // Source eye positions
    const srcLeftEye = srcPoints.leftEye;
    const srcRightEye = srcPoints.rightEye;

    // Calculate source eye vector
    const srcDx = srcRightEye.x - srcLeftEye.x;
    const srcDy = srcRightEye.y - srcLeftEye.y;
    const srcDist = Math.sqrt(srcDx * srcDx + srcDy * srcDy);
    const srcAngle = Math.atan2(srcDy, srcDx);

    // Target: eyes horizontal, separated by targetEyeDistance pixels
    const targetDist = targetEyeDistance;  // e.g., 150 pixels
    const targetAngle = 0;  // horizontal (or add offset for rotation)

    // Compute scale and rotation
    const scale = targetDist / srcDist;
    const rotation = targetAngle - srcAngle;

    // Similarity transform matrix components
    const cos = Math.cos(rotation) * scale;
    const sin = Math.sin(rotation) * scale;

    // Source eye midpoint
    const srcMidX = (srcLeftEye.x + srcRightEye.x) / 2;
    const srcMidY = (srcLeftEye.y + srcRightEye.y) / 2;

    // Translation: map source midpoint to viewport center
    const tx = cx - (cos * srcMidX - sin * srcMidY);
    const ty = cy - (sin * srcMidX + cos * srcMidY);

    // Return CSS matrix parameters
    return {
        a: cos,    // scale * cos(rotation)
        b: sin,    // scale * sin(rotation)
        c: -sin,   // -scale * sin(rotation)
        d: cos,    // scale * cos(rotation)
        tx: tx,    // x translation
        ty: ty     // y translation
    };
}
```

### Step 3: Apply Transform

Apply the transformation using CSS `matrix()`:

```javascript
// CSS matrix(a, b, c, d, tx, ty) applies:
// x' = a*x + c*y + tx
// y' = b*x + d*y + ty

element.style.transformOrigin = '0 0';
element.style.transform = `matrix(${a}, ${b}, ${c}, ${d}, ${tx}, ${ty})`;
```

### Mathematical Form

The similarity transform matrix is:

```
┌                      ┐   ┌     ┐   ┌    ┐
│ s·cos(θ)  -s·sin(θ)  │   │  x  │   │ tx │
│                      │ × │     │ + │    │
│ s·sin(θ)   s·cos(θ)  │   │  y  │   │ ty │
└                      ┘   └     ┘   └    ┘
```

Where:
- `s` = scale factor = targetEyeDistance / sourceEyeDistance
- `θ` = rotation angle = targetAngle - sourceAngle
- `tx`, `ty` = translation to center the face

