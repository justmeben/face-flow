"""Calculate head pose (roll, yaw, pitch) from facial landmarks."""

import numpy as np
import cv2
from typing import Dict, List, Optional, Tuple


# 3D model points for a generic face (in arbitrary units, centered at nose)
# These correspond to: nose tip, chin, left eye corner, right eye corner,
# left mouth corner, right mouth corner
MODEL_POINTS_3D = np.array([
    (0.0, 0.0, 0.0),             # Nose tip (landmark 30)
    (0.0, -330.0, -65.0),        # Chin (landmark 8)
    (-225.0, 170.0, -135.0),     # Left eye left corner (landmark 36)
    (225.0, 170.0, -135.0),      # Right eye right corner (landmark 45)
    (-150.0, -150.0, -125.0),    # Left mouth corner (landmark 48)
    (150.0, -150.0, -125.0)      # Right mouth corner (landmark 54)
], dtype=np.float64)


def get_camera_matrix(image_width: int, image_height: int) -> np.ndarray:
    """Create a camera matrix assuming the camera is at the image center."""
    focal_length = image_width  # Approximate focal length
    center = (image_width / 2, image_height / 2)
    return np.array([
        [focal_length, 0, center[0]],
        [0, focal_length, center[1]],
        [0, 0, 1]
    ], dtype=np.float64)


def extract_key_landmarks(landmarks: List[Tuple[int, int]]) -> Optional[np.ndarray]:
    """
    Extract the 6 key landmarks for pose estimation from 68-point facial landmarks.

    face_recognition returns landmarks as a dict with keys like 'nose_tip', 'chin', etc.
    We need to convert to the 6 points used for pose estimation.
    """
    if isinstance(landmarks, dict):
        # face_recognition format: dict with named landmark groups
        try:
            # Get specific points from each group
            nose_tip = landmarks['nose_tip'][2]  # Middle of nose tip
            chin = landmarks['chin'][8]  # Bottom of chin
            left_eye = landmarks['left_eye'][0]  # Left corner of left eye
            right_eye = landmarks['right_eye'][3]  # Right corner of right eye
            left_mouth = landmarks['top_lip'][0]  # Left corner of mouth
            right_mouth = landmarks['top_lip'][6]  # Right corner of mouth

            return np.array([
                nose_tip,
                chin,
                left_eye,
                right_eye,
                left_mouth,
                right_mouth
            ], dtype=np.float64)
        except (KeyError, IndexError):
            return None
    elif isinstance(landmarks, list) and len(landmarks) >= 68:
        # Standard 68-point format
        return np.array([
            landmarks[30],  # Nose tip
            landmarks[8],   # Chin
            landmarks[36],  # Left eye left corner
            landmarks[45],  # Right eye right corner
            landmarks[48],  # Left mouth corner
            landmarks[54]   # Right mouth corner
        ], dtype=np.float64)

    return None


def calculate_rotation(
    landmarks: dict,
    image_width: int,
    image_height: int
) -> Dict[str, float]:
    """
    Calculate roll, yaw, and pitch from facial landmarks.

    Returns angles in degrees:
    - roll: head tilt (ear to shoulder), positive = tilted right
    - yaw: left/right rotation, positive = looking right
    - pitch: up/down tilt, positive = looking up
    """
    result = {"roll": 0.0, "yaw": 0.0, "pitch": 0.0}

    # Extract key landmarks
    image_points = extract_key_landmarks(landmarks)
    if image_points is None:
        return result

    # Camera parameters
    camera_matrix = get_camera_matrix(image_width, image_height)
    dist_coeffs = np.zeros((4, 1))  # Assuming no lens distortion

    try:
        # Solve for pose
        success, rotation_vector, translation_vector = cv2.solvePnP(
            MODEL_POINTS_3D,
            image_points,
            camera_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE
        )

        if not success:
            return result

        # Convert rotation vector to rotation matrix
        rotation_matrix, _ = cv2.Rodrigues(rotation_vector)

        # Extract Euler angles from rotation matrix
        # Using the convention: R = Rz(yaw) * Ry(pitch) * Rx(roll)
        sy = np.sqrt(rotation_matrix[0, 0] ** 2 + rotation_matrix[1, 0] ** 2)

        if sy > 1e-6:
            roll = np.arctan2(rotation_matrix[2, 1], rotation_matrix[2, 2])
            pitch = np.arctan2(-rotation_matrix[2, 0], sy)
            yaw = np.arctan2(rotation_matrix[1, 0], rotation_matrix[0, 0])
        else:
            roll = np.arctan2(-rotation_matrix[1, 2], rotation_matrix[1, 1])
            pitch = np.arctan2(-rotation_matrix[2, 0], sy)
            yaw = 0

        # Convert to degrees
        result["roll"] = float(np.degrees(roll))
        result["yaw"] = float(np.degrees(yaw))
        result["pitch"] = float(np.degrees(pitch))

    except Exception as e:
        pass

    return result


def calculate_simple_roll(landmarks: dict) -> float:
    """
    Calculate a simple roll angle based on eye positions.
    Useful as a fallback or sanity check.
    """
    try:
        if isinstance(landmarks, dict):
            left_eye = landmarks['left_eye']
            right_eye = landmarks['right_eye']
            # Get center of each eye
            left_center = np.mean(left_eye, axis=0)
            right_center = np.mean(right_eye, axis=0)
        else:
            return 0.0

        # Calculate angle between eyes
        dx = right_center[0] - left_center[0]
        dy = right_center[1] - left_center[1]
        angle = np.degrees(np.arctan2(dy, dx))

        return float(angle)
    except Exception:
        return 0.0


if __name__ == "__main__":
    # Test with sample landmarks
    sample_landmarks = {
        'chin': [(x, 100 + x*2) for x in range(17)],
        'left_eye': [(100 + x*5, 80) for x in range(6)],
        'right_eye': [(200 + x*5, 80) for x in range(6)],
        'nose_tip': [(150 + x*5, 120) for x in range(5)],
        'top_lip': [(120 + x*8, 150) for x in range(12)],
    }
    print(calculate_rotation(sample_landmarks, 640, 480))
