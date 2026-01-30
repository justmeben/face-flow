// ============ Landmark Editor Mode ============
// Manual landmark placement for photos with failed face detection

import { state } from './state.js';
import { getSubjectData } from './utils.js';
import { updateSidebarVisibility } from './navigation.js';
import { renderPreviewPhoto } from './preview.js';

export function setupEditMode() {
    document.getElementById('setLandmarksBtn').addEventListener('click', toggleEditMode);
    document.getElementById('editorCancelBtn').addEventListener('click', exitEditMode);
    document.getElementById('editorResetBtn').addEventListener('click', resetEditorLandmarks);
    document.getElementById('editorSaveBtn').addEventListener('click', saveEditorLandmarks);

    document.getElementById('editCanvas').addEventListener('click', handleEditorClick);

    document.querySelectorAll('.landmark-item').forEach(item => {
        item.addEventListener('click', () => setEditorLandmark(item.dataset.landmark));
    });
}

function toggleEditMode() {
    if (state.editMode) {
        exitEditMode();
    } else {
        enterEditMode();
    }
}

function enterEditMode() {
    if (!state.previewPhoto || !state.previewImage) return;

    state.editMode = true;
    state.editorImage = state.previewImage;
    resetEditorLandmarks();

    // Update button text and sidebar visibility
    document.getElementById('setLandmarksBtn').textContent = 'Return to Preview';
    updateSidebarVisibility();

    // Disable scrubber
    document.getElementById('previewScrubber').classList.add('disabled');

    // Hide normal photo, show canvas
    const container = document.getElementById('previewContainer');
    const existing = container.querySelector('.photo');
    if (existing) existing.style.display = 'none';

    document.getElementById('previewAge').classList.add('hidden');
    document.getElementById('editorSidebar').classList.add('visible');
    document.getElementById('debugSidebar').classList.remove('visible');

    const canvas = document.getElementById('editCanvas');
    canvas.classList.add('visible');
    renderEditorCanvas();

    // Load existing landmarks if available
    const subject = getSubjectData(state.previewPhoto);
    if (subject?.landmarks) {
        loadExistingLandmarks(subject.landmarks);
    }
}

export function exitEditMode() {
    state.editMode = false;
    state.editorImage = null;

    // Reset button text and sidebar visibility
    document.getElementById('setLandmarksBtn').textContent = 'Fix Detection';
    updateSidebarVisibility();

    // Re-enable scrubber
    document.getElementById('previewScrubber').classList.remove('disabled');

    document.getElementById('editCanvas').classList.remove('visible');
    document.getElementById('editorSidebar').classList.remove('visible');

    const container = document.getElementById('previewContainer');
    const existing = container.querySelector('.photo');
    if (existing) existing.style.display = '';

    if (document.getElementById('showAgeCheck').checked) {
        document.getElementById('previewAge').classList.remove('hidden');
    }

    if (state.debugMode) {
        document.getElementById('debugSidebar').classList.add('visible');
    }

    renderPreviewPhoto();
}

function loadExistingLandmarks(lm) {
    const avg = arr => arr ? ({
        x: Math.round(arr.reduce((s, p) => s + p[0], 0) / arr.length),
        y: Math.round(arr.reduce((s, p) => s + p[1], 0) / arr.length)
    }) : null;

    state.editorLandmarks.leftEye = avg(lm.left_eye);
    state.editorLandmarks.rightEye = avg(lm.right_eye);
    state.editorLandmarks.mouth = avg(lm.top_lip);

    renderEditorCanvas();
    updateEditorUI();
}

export function setEditorLandmark(name) {
    state.currentLandmark = name;
    document.querySelectorAll('.landmark-item').forEach(item => {
        item.classList.toggle('active', item.dataset.landmark === name);
    });
}

function resetEditorLandmarks() {
    // Reset to saved state if available, otherwise clear
    const subject = getSubjectData(state.previewPhoto);
    if (subject?.landmarks) {
        loadExistingLandmarks(subject.landmarks);
    } else {
        state.editorLandmarks = { leftEye: null, rightEye: null, mouth: null };
        renderEditorCanvas();
        updateEditorUI();
    }
    setEditorLandmark('leftEye');
}

function handleEditorClick(e) {
    if (!state.editorImage) return;

    const canvas = document.getElementById('editCanvas');
    const rect = canvas.getBoundingClientRect();
    const scaleX = state.editorImage.width / rect.width;
    const scaleY = state.editorImage.height / rect.height;

    state.editorLandmarks[state.currentLandmark] = {
        x: Math.round((e.clientX - rect.left) * scaleX),
        y: Math.round((e.clientY - rect.top) * scaleY)
    };

    // Advance to next
    if (state.currentLandmark === 'leftEye') setEditorLandmark('rightEye');
    else if (state.currentLandmark === 'rightEye') setEditorLandmark('mouth');
    else setEditorLandmark('leftEye');

    renderEditorCanvas();
    updateEditorUI();
}

function renderEditorCanvas() {
    if (!state.editorImage) return;

    const canvas = document.getElementById('editCanvas');
    const ctx = canvas.getContext('2d');
    const container = document.getElementById('preview-content');

    const maxW = container.clientWidth - 40;
    const maxH = container.clientHeight - 40;
    const scale = Math.min(maxW / state.editorImage.width, maxH / state.editorImage.height);

    canvas.width = state.editorImage.width * scale;
    canvas.height = state.editorImage.height * scale;

    ctx.drawImage(state.editorImage, 0, 0, canvas.width, canvas.height);

    const drawPoint = (point, color, label) => {
        if (!point) return;
        const x = point.x * scale;
        const y = point.y * scale;
        const r = 8;

        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();

        ctx.fillStyle = '#fff';
        ctx.font = 'bold 12px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(label, x, y - r - 5);
    };

    drawPoint(state.editorLandmarks.leftEye, '#4CAF50', 'L');
    drawPoint(state.editorLandmarks.rightEye, '#2196F3', 'R');
    drawPoint(state.editorLandmarks.mouth, '#FF9800', 'M');

    if (state.editorLandmarks.leftEye && state.editorLandmarks.rightEye) {
        ctx.strokeStyle = 'rgba(255,255,255,0.5)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(state.editorLandmarks.leftEye.x * scale, state.editorLandmarks.leftEye.y * scale);
        ctx.lineTo(state.editorLandmarks.rightEye.x * scale, state.editorLandmarks.rightEye.y * scale);
        ctx.stroke();
    }
}

function updateEditorUI() {
    const fmt = p => p ? `(${p.x}, ${p.y})` : 'Click to set';
    document.getElementById('editorLeftEyeCoords').textContent = fmt(state.editorLandmarks.leftEye);
    document.getElementById('editorRightEyeCoords').textContent = fmt(state.editorLandmarks.rightEye);
    document.getElementById('editorMouthCoords').textContent = fmt(state.editorLandmarks.mouth);

    document.getElementById('editorLeftEye').classList.toggle('set', !!state.editorLandmarks.leftEye);
    document.getElementById('editorRightEye').classList.toggle('set', !!state.editorLandmarks.rightEye);
    document.getElementById('editorMouth').classList.toggle('set', !!state.editorLandmarks.mouth);

    const allSet = state.editorLandmarks.leftEye && state.editorLandmarks.rightEye && state.editorLandmarks.mouth;
    document.getElementById('editorSaveBtn').disabled = !allSet;
}

async function saveEditorLandmarks() {
    const payload = {
        filename: state.previewPhoto.filename,
        landmarks: {
            left_eye: state.editorLandmarks.leftEye,
            right_eye: state.editorLandmarks.rightEye,
            mouth: state.editorLandmarks.mouth
        }
    };

    try {
        const response = await fetch('/api/save-landmarks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            showEditorStatus('Saved!', 'success');

            // Update local data
            if (!state.previewPhoto.faces) state.previewPhoto.faces = {};
            if (!state.previewPhoto.faces.subject) state.previewPhoto.faces.subject = {};
            state.previewPhoto.faces.subject.detected = true;
            state.previewPhoto.faces.subject.landmarks = {
                left_eye: [[state.editorLandmarks.leftEye.x, state.editorLandmarks.leftEye.y]],
                right_eye: [[state.editorLandmarks.rightEye.x, state.editorLandmarks.rightEye.y]],
                top_lip: [[state.editorLandmarks.mouth.x, state.editorLandmarks.mouth.y]]
            };

            if (state.previewPhoto.faces.ben) {
                delete state.previewPhoto.faces.ben;
            }

            // Rebuild previewPhotos
            state.previewPhotos = state.allPhotos.filter(p => getSubjectData(p)?.detected === true);
            state.previewPhotos.sort((a, b) => (a.metadata?.date_taken || '').localeCompare(b.metadata?.date_taken || ''));

            setTimeout(() => exitEditMode(), 1000);
        } else {
            const result = await response.json();
            showEditorStatus(result.error || 'Save failed', 'error');
        }
    } catch (err) {
        showEditorStatus('Server error - run: python server.py', 'error');
    }
}

function showEditorStatus(message, type) {
    const el = document.getElementById('editorStatus');
    el.textContent = message;
    el.className = `status-message ${type}`;
    setTimeout(() => { el.className = 'status-message'; }, 3000);
}
