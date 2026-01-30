// ============ Shared Utilities ============
// Functions used across multiple modules

import { state } from './state.js';

/**
 * Migrate old "ben" key to "subject" in face data
 */
export function migrateFaceData(data) {
    if (!data || !data.photos) return data;
    for (const photo of data.photos) {
        if (photo.faces?.ben && !photo.faces?.subject) {
            photo.faces.subject = photo.faces.ben;
            delete photo.faces.ben;
        }
    }
    return data;
}

/**
 * Get subject data from a photo, handling both "subject" and legacy "ben" keys
 */
export function getSubjectData(photo) {
    if (!photo?.faces) return null;
    return photo.faces.subject || photo.faces.ben || null;
}

/**
 * Calculate age based on photo date and birth date
 */
export function calculateAge(photoDate) {
    if (!photoDate) return null;
    const date = new Date(photoDate);
    if (isNaN(date.getTime())) return null;
    const birth = new Date(state.birthDate);
    const diffMs = date - birth;
    const diffYears = diffMs / (1000 * 60 * 60 * 24 * 365.25);
    return diffYears;
}

/**
 * Get face anchor points from landmarks
 */
export function getFacePoints(landmarks) {
    if (!landmarks?.left_eye || !landmarks?.right_eye || !landmarks?.top_lip) return null;

    const avg = arr => ({
        x: arr.reduce((s, p) => s + p[0], 0) / arr.length,
        y: arr.reduce((s, p) => s + p[1], 0) / arr.length
    });

    return {
        leftEye: avg(landmarks.left_eye),
        rightEye: avg(landmarks.right_eye),
        mouth: avg(landmarks.top_lip)
    };
}

/**
 * Show a toast notification
 * @param {string} message - The message to display
 * @param {string} type - 'success', 'error', or 'info' (default: 'info')
 * @param {number} duration - Duration in ms (default: 3000)
 */
export function showToast(message, type = 'info', duration = 3000) {
    // Get or create toast container
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    container.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(() => {
        toast.classList.add('show');
    });

    // Remove after duration
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}
