// ============ Debug Mode ============
// Debug overlay rendering and debug sidebar info

import { state } from './state.js';
import { getSubjectData, calculateAge, showToast } from './utils.js';
import { renderPreviewPhoto, updatePreviewScrubber } from './preview.js';

export function setupDebugMode() {
    const btn = document.getElementById('debugModeBtn');
    btn.addEventListener('click', () => {
        state.debugMode = !state.debugMode;
        btn.classList.toggle('active', state.debugMode);
        document.getElementById('debugSidebar').classList.toggle('visible', state.debugMode);
        renderPreviewPhoto();
        if (state.debugMode && state.previewPhoto) updateDebugInfo();
    });

    document.getElementById('debugSaveDateBtn').addEventListener('click', saveDebugDate);
    document.getElementById('debugSaveAgeBtn').addEventListener('click', saveDebugAge);
}

export function renderDebugOverlay(canvas, photo, image, transformScale = 1) {
    const ctx = canvas.getContext('2d');
    const faces = photo.faces || {};
    const subject = getSubjectData(photo);

    // Scale overlay sizes inversely to transform scale so they appear constant on screen
    // transformScale > 1 means zoomed in, so we draw smaller; < 1 means zoomed out, draw larger
    const inverseScale = 1 / transformScale;
    const lineWidth = 2 * inverseScale;
    const dotRadius = 4 * inverseScale;
    const fontSize = 12 * inverseScale;
    const labelHeight = 18 * inverseScale;
    const labelPadding = 4 * inverseScale;

    // Draw other faces
    if (faces.others) {
        faces.others.forEach(face => {
            if (face.bounding_box) {
                const b = face.bounding_box;
                ctx.strokeStyle = '#FFD700';
                ctx.lineWidth = lineWidth;
                ctx.strokeRect(b.x, b.y, b.width, b.height);
            }
        });
    }

    // Draw subject
    if (subject?.detected) {
        if (subject.bounding_box) {
            const b = subject.bounding_box;
            ctx.strokeStyle = '#4CAF50';
            ctx.lineWidth = lineWidth;
            ctx.strokeRect(b.x, b.y, b.width, b.height);

            ctx.fillStyle = '#4CAF50';
            const labelWidth = 50 * inverseScale;
            const labelGap = 2 * inverseScale;
            ctx.fillRect(b.x, b.y - labelHeight - labelGap, labelWidth, labelHeight);
            ctx.fillStyle = '#000';
            ctx.font = `bold ${fontSize}px sans-serif`;
            ctx.fillText('Subject', b.x + labelPadding, b.y - labelPadding - labelGap);
        }

        if (subject.landmarks) {
            ctx.fillStyle = '#00FFFF';
            Object.values(subject.landmarks).forEach(points => {
                points.forEach(([x, y]) => {
                    ctx.beginPath();
                    ctx.arc(x, y, dotRadius, 0, Math.PI * 2);
                    ctx.fill();
                });
            });
        }
    }
}

export function updateDebugInfo() {
    if (!state.previewPhoto) return;

    const meta = state.previewPhoto.metadata || {};
    const faces = state.previewPhoto.faces || {};
    const subject = getSubjectData(state.previewPhoto) || {};

    document.getElementById('debugFilename').textContent = state.previewPhoto.filename;

    // Age display and input
    const age = calculateAge(meta.date_taken);
    document.getElementById('debugAge').textContent = age !== null ? age.toFixed(2) : 'Unknown';
    document.getElementById('debugAgeInput').value = age !== null ? age.toFixed(2) : '';

    // Date display and input
    document.getElementById('debugDate').textContent = meta.date_taken
        ? new Date(meta.date_taken).toLocaleDateString()
        : 'Unknown';

    const dateInput = document.getElementById('debugDateInput');
    if (meta.date_taken) {
        const d = new Date(meta.date_taken);
        dateInput.value = d.toISOString().slice(0, 16);
    } else {
        dateInput.value = '';
    }

    document.getElementById('debugSize').textContent = meta.width && meta.height
        ? `${meta.width} x ${meta.height}`
        : 'Unknown';

    document.getElementById('debugSubjectDetected').textContent = subject.detected ? 'Yes' : 'No';
    document.getElementById('debugSubjectConfidence').textContent = subject.detected
        ? `${(subject.confidence * 100).toFixed(1)}%`
        : '-';
    document.getElementById('debugSubjectPosition').textContent = subject.center
        ? `(${subject.center.x}, ${subject.center.y})`
        : '-';
    document.getElementById('debugSubjectSize').textContent = subject.scale
        ? `${subject.scale.face_width_px} x ${subject.scale.face_height_px}px`
        : '-';

    document.getElementById('debugTotalFaces').textContent = faces.total_count || 0;
    document.getElementById('debugOtherFaces').textContent = faces.others?.length || 0;

    const lm = subject.landmarks || {};
    const avg = arr => arr && arr.length ?
        `(${Math.round(arr.reduce((s, p) => s + p[0], 0) / arr.length)}, ${Math.round(arr.reduce((s, p) => s + p[1], 0) / arr.length)})` : '-';

    document.getElementById('debugLeftEye').textContent = avg(lm.left_eye);
    document.getElementById('debugRightEye').textContent = avg(lm.right_eye);
    document.getElementById('debugMouth').textContent = avg(lm.top_lip);

    document.getElementById('debugSubjectBox').classList.toggle('not-found', !subject.detected);
}

async function saveDebugDate() {
    const input = document.getElementById('debugDateInput');
    const newDate = input.value;
    if (!newDate || !state.previewPhoto) return;

    const isoDate = new Date(newDate).toISOString().slice(0, 19);

    try {
        const response = await fetch('/api/save-date', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: state.previewPhoto.filename,
                date_taken: isoDate
            })
        });

        if (response.ok) {
            if (!state.previewPhoto.metadata) state.previewPhoto.metadata = {};
            state.previewPhoto.metadata.date_taken = isoDate;
            state.previewPhoto.metadata.date_source = 'manual';

            state.previewPhotos.sort((a, b) => (a.metadata?.date_taken || '').localeCompare(b.metadata?.date_taken || ''));

            updateDebugInfo();
            updatePreviewScrubber();
            renderPreviewPhoto();
            showToast('Date saved!', 'success');
        } else {
            const result = await response.json();
            showToast('Save failed: ' + (result.error || 'Unknown error'), 'error');
        }
    } catch (err) {
        showToast('Server error - make sure python server.py is running', 'error');
    }
}

async function saveDebugAge() {
    const input = document.getElementById('debugAgeInput');
    const newAge = parseFloat(input.value);
    if (isNaN(newAge) || !state.previewPhoto) return;

    // Calculate the date from age and birth date
    const birth = new Date(state.birthDate);
    const photoDate = new Date(birth.getTime() + newAge * 365.25 * 24 * 60 * 60 * 1000);
    const isoDate = photoDate.toISOString().slice(0, 19);

    try {
        const response = await fetch('/api/save-date', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: state.previewPhoto.filename,
                date_taken: isoDate
            })
        });

        if (response.ok) {
            if (!state.previewPhoto.metadata) state.previewPhoto.metadata = {};
            state.previewPhoto.metadata.date_taken = isoDate;
            state.previewPhoto.metadata.date_source = 'manual';

            state.previewPhotos.sort((a, b) => (a.metadata?.date_taken || '').localeCompare(b.metadata?.date_taken || ''));

            updateDebugInfo();
            updatePreviewScrubber();
            renderPreviewPhoto();
            showToast('Age saved!', 'success');
        } else {
            const result = await response.json();
            showToast('Save failed: ' + (result.error || 'Unknown error'), 'error');
        }
    } catch (err) {
        showToast('Server error - make sure python server.py is running', 'error');
    }
}
