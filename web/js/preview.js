// ============ Preview View ============
// Photo preview rendering, scrubbing, and face transformations

import { state } from './state.js';
import { getSubjectData, calculateAge, getFacePoints, showToast } from './utils.js';
import { renderDebugOverlay, updateDebugInfo } from './debug.js';

export function setupPreviewView() {
    const scaleSlider = document.getElementById('previewScale');
    const scaleValue = document.getElementById('previewScaleValue');
    const angleInput = document.getElementById('previewAngle');
    const track = document.getElementById('previewTrack');
    const thumb = document.getElementById('previewThumb');

    scaleSlider.addEventListener('input', () => {
        state.targetFaceWidth = parseInt(scaleSlider.value);
        scaleValue.textContent = state.targetFaceWidth + 'px';
        renderPreviewPhoto();
    });

    angleInput.addEventListener('input', () => renderPreviewPhoto());

    ['scaleCheck', 'rotateCheck'].forEach(id => {
        document.getElementById(id).addEventListener('change', () => renderPreviewPhoto());
    });

    document.getElementById('showAgeCheck').addEventListener('change', (e) => {
        document.getElementById('previewAge').classList.toggle('hidden', !e.target.checked);
    });

    thumb.addEventListener('mousedown', (e) => { state.isDragging = true; e.preventDefault(); });
    document.addEventListener('mousemove', (e) => { if (state.isDragging) handleScrub(e); });
    document.addEventListener('mouseup', () => { state.isDragging = false; });
    track.addEventListener('click', handleScrub);

    document.getElementById('previewContainer').addEventListener('wheel', (e) => {
        if (state.editMode) return;
        e.preventDefault();
        state.targetFaceWidth = Math.max(50, Math.min(300, state.targetFaceWidth + (e.deltaY > 0 ? -10 : 10)));
        scaleSlider.value = state.targetFaceWidth;
        scaleValue.textContent = state.targetFaceWidth + 'px';
        renderPreviewPhoto();
    });

    // Slideshow
    const slideshowBtn = document.getElementById('slideshowBtn');
    const slideshowIntervalInput = document.getElementById('slideshowInterval');

    slideshowBtn.addEventListener('click', () => {
        if (state.slideshowTimer) {
            clearInterval(state.slideshowTimer);
            state.slideshowTimer = null;
            slideshowBtn.textContent = 'Play';
            slideshowBtn.classList.remove('active');
        } else {
            const interval = parseInt(slideshowIntervalInput.value) || 200;
            state.slideshowTimer = setInterval(() => {
                const nextIndex = (state.previewIndex + 1) % state.previewPhotos.length;
                loadPreviewPhoto(nextIndex);
            }, interval);
            slideshowBtn.textContent = 'Stop';
            slideshowBtn.classList.add('active');
        }
    });

    // Delete button
    document.getElementById('deletePhotoBtn').addEventListener('click', deleteCurrentPhoto);
}

async function deleteCurrentPhoto() {
    if (!state.previewPhoto || state.editMode) return;

    const filename = state.previewPhoto.filename;
    if (!confirm(`Delete "${filename}"?\n\nThis will permanently delete the photo file and remove it from the database.`)) {
        return;
    }

    try {
        const response = await fetch('/api/delete-photo', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        });

        if (response.ok) {
            const previewIdx = state.previewPhotos.findIndex(p => p.filename === filename);
            const allIdx = state.allPhotos.findIndex(p => p.filename === filename);

            if (previewIdx !== -1) state.previewPhotos.splice(previewIdx, 1);
            if (allIdx !== -1) state.allPhotos.splice(allIdx, 1);

            if (state.previewPhotos.length === 0) {
                state.previewPhoto = null;
                state.previewImage = null;
                const container = document.getElementById('previewContainer');
                const existing = container.querySelector('.photo');
                if (existing) existing.remove();
                document.getElementById('previewAge').textContent = 'No photos';
                updatePreviewScrubber();
            } else {
                const newIndex = Math.min(state.previewIndex, state.previewPhotos.length - 1);
                loadPreviewPhoto(newIndex);
            }

            showToast(`Deleted: ${filename}`, 'success');
        } else {
            const result = await response.json();
            showToast('Delete failed: ' + (result.error || 'Unknown error'), 'error');
        }
    } catch (err) {
        showToast('Server error - make sure python server.py is running', 'error');
    }
}

function handleScrub(e) {
    if (state.editMode) return;
    const track = document.getElementById('previewTrack');
    const rect = track.getBoundingClientRect();
    const percent = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const index = Math.round(percent * (state.previewPhotos.length - 1));
    loadPreviewPhoto(index);
}

export function loadPreviewPhoto(index) {
    if (index < 0 || index >= state.previewPhotos.length) return;
    state.previewIndex = index;
    state.previewPhoto = state.previewPhotos[index];

    const img = new Image();
    img.onload = () => {
        state.previewImage = img;
        renderPreviewPhoto();
        updatePreviewScrubber();
        if (state.debugMode) updateDebugInfo();
    };
    img.src = `../photos/${state.previewPhoto.filename}`;
}

export function updatePreviewScrubber() {
    const percent = state.previewPhotos.length > 1 ? (state.previewIndex / (state.previewPhotos.length - 1)) * 100 : 0;
    document.getElementById('previewProgress').style.width = `${percent}%`;
    document.getElementById('previewThumb').style.left = `${percent}%`;

    const age = calculateAge(state.previewPhoto?.metadata?.date_taken);
    const ageStr = age !== null ? `Age: ${age.toFixed(2)}` : '';
    document.getElementById('previewInfo').textContent = `Photo ${state.previewIndex + 1}/${state.previewPhotos.length}  ${ageStr}`;
}

export function navigatePhoto(delta) {
    if (state.currentPage !== 'preview' || state.editMode) return;
    const newIndex = state.previewIndex + delta;
    if (newIndex >= 0 && newIndex < state.previewPhotos.length) {
        loadPreviewPhoto(newIndex);
    }
}

function computeSimilarityTransform(srcPoints, viewport) {
    const cx = viewport.width / 2;
    const cy = viewport.height / 2;

    const doScale = document.getElementById('scaleCheck').checked;
    const doRotate = document.getElementById('rotateCheck').checked;
    const angleOffset = (parseInt(document.getElementById('previewAngle').value) || 0) * Math.PI / 180;

    const srcDx = srcPoints.rightEye.x - srcPoints.leftEye.x;
    const srcDy = srcPoints.rightEye.y - srcPoints.leftEye.y;
    const srcDist = Math.sqrt(srcDx * srcDx + srcDy * srcDy);
    const srcAngle = Math.atan2(srcDy, srcDx);

    const scale = doScale ? state.targetFaceWidth / srcDist : 1;
    const rotation = doRotate ? angleOffset - srcAngle : angleOffset;

    const cos = Math.cos(rotation) * scale;
    const sin = Math.sin(rotation) * scale;

    const srcMidX = (srcPoints.leftEye.x + srcPoints.rightEye.x) / 2;
    const srcMidY = (srcPoints.leftEye.y + srcPoints.rightEye.y) / 2;

    const tx = cx - (cos * srcMidX - sin * srcMidY);
    const ty = cy - (sin * srcMidX + cos * srcMidY);

    return [cos, sin, -sin, cos, tx, ty];
}

export function renderPreviewPhoto() {
    if (!state.previewImage || !state.previewPhoto || state.editMode) return;

    const container = document.getElementById('previewContainer');
    const existing = container.querySelector('.photo');
    if (existing) existing.remove();

    const subject = getSubjectData(state.previewPhoto);
    const srcPoints = getFacePoints(subject?.landmarks);

    if (!srcPoints) return;

    const viewport = container.getBoundingClientRect();
    const [a, b, c, d, e, f] = computeSimilarityTransform(srcPoints, viewport);

    const wrapper = document.createElement('div');
    wrapper.className = 'photo';
    const imgEl = document.createElement('img');
    imgEl.src = state.previewImage.src;
    imgEl.style.width = `${state.previewImage.width}px`;
    imgEl.style.height = `${state.previewImage.height}px`;
    wrapper.appendChild(imgEl);

    // Add debug overlays if debug mode is on
    if (state.debugMode) {
        const canvas = document.createElement('canvas');
        canvas.className = 'debug-overlay';
        canvas.width = state.previewImage.width;
        canvas.height = state.previewImage.height;
        canvas.style.width = `${state.previewImage.width}px`;
        canvas.style.height = `${state.previewImage.height}px`;
        // Calculate the transform scale to adjust overlay sizes
        const transformScale = Math.sqrt(a * a + b * b);
        renderDebugOverlay(canvas, state.previewPhoto, state.previewImage, transformScale);
        wrapper.appendChild(canvas);
    }

    wrapper.style.transform = `matrix(${a}, ${b}, ${c}, ${d}, ${e}, ${f})`;
    container.appendChild(wrapper);

    // Update age display
    const age = calculateAge(state.previewPhoto.metadata?.date_taken);
    document.getElementById('previewAge').textContent = age !== null ? age.toFixed(2) : '';
}
