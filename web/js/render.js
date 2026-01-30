// ============ Render View ============
// Video rendering UI and progress tracking

import { state } from './state.js';
import { showToast } from './utils.js';

let renderPollInterval = null;
let capabilities = null;
let lastOutputPath = null;
let lastOverlayPath = null;
let lastAgeMode = null;

export function setupRenderPage() {
    // Load capabilities on init
    loadCapabilities();

    // Resolution presets
    document.querySelectorAll('.resolution-preset').forEach(btn => {
        btn.addEventListener('click', () => {
            const width = parseInt(btn.dataset.width);
            const height = parseInt(btn.dataset.height);
            document.getElementById('renderWidth').value = width;
            document.getElementById('renderHeight').value = height;
        });
    });

    // Age mode hint update
    document.getElementById('renderAgeMode').addEventListener('change', updateAgeModeHint);

    // Blur slider update
    const blurSlider = document.getElementById('renderBlur');
    const blurValue = document.getElementById('renderBlurValue');
    blurSlider.addEventListener('input', () => {
        const val = parseInt(blurSlider.value);
        blurValue.textContent = val === 0 ? 'Off' : `${val}px`;
    });

    // Start render button
    document.getElementById('startRenderBtn').addEventListener('click', startRender);

    // Cancel render button
    document.getElementById('cancelRenderBtn').addEventListener('click', cancelRender);

    // Sidebar open output folder button
    document.getElementById('openOutFolderBtn').addEventListener('click', openOutputFolder);

    // Complete panel buttons
    document.getElementById('openOutFolderBtnComplete').addEventListener('click', openOutputFolder);
    document.getElementById('openVideoBtn').addEventListener('click', openRenderedVideo);
    document.getElementById('openOverlayBtn').addEventListener('click', openOverlayVideo);

    // Initialize frame range when we have data
    updateFrameRange();
}

function updateAgeModeHint() {
    const mode = document.getElementById('renderAgeMode').value;
    const hint = document.getElementById('ageModeHint');

    const hints = {
        'show': 'Age text rendered directly on video',
        'hide': 'Clean video without age text',
        'separate': 'Two videos: clean video + greenscreen overlay for chroma key compositing',
        'overlay_only': 'Only greenscreen overlay video for chroma key compositing'
    };

    hint.textContent = hints[mode] || '';
}

async function loadCapabilities() {
    try {
        const response = await fetch('/api/render-capabilities');
        capabilities = await response.json();

        const formatSelect = document.getElementById('renderFormat');
        formatSelect.innerHTML = '';

        if (capabilities.formats && capabilities.formats.length > 0) {
            capabilities.formats.forEach(format => {
                const option = document.createElement('option');
                option.value = format;
                option.textContent = format === 'mp4' ? 'MP4 (H.264)' :
                                   format === 'gif' ? 'GIF' :
                                   format === 'png_sequence' ? 'PNG Sequence' : format;
                formatSelect.appendChild(option);
            });
        }

    } catch (err) {
        console.error('Failed to load render capabilities:', err);
    }
}

/**
 * Auto-sync transform settings from preview controls.
 * Called when switching to render page.
 */
export function syncFromPreview() {
    const faceWidth = document.getElementById('previewScale')?.value;
    const angle = document.getElementById('previewAngle')?.value;
    const doScale = document.getElementById('scaleCheck')?.checked;
    const doRotate = document.getElementById('rotateCheck')?.checked;
    const showAge = document.getElementById('showAgeCheck')?.checked;
    const frameDuration = document.getElementById('slideshowInterval')?.value;

    if (faceWidth) document.getElementById('renderFaceWidth').value = faceWidth;
    if (angle !== undefined) document.getElementById('renderAngle').value = angle;
    if (doScale !== undefined) document.getElementById('renderScale').checked = doScale;
    if (doRotate !== undefined) document.getElementById('renderRotate').checked = doRotate;
    if (frameDuration) document.getElementById('renderFrameDuration').value = frameDuration;

    // Sync age mode from preview checkbox
    if (showAge !== undefined) {
        document.getElementById('renderAgeMode').value = showAge ? 'show' : 'hide';
        updateAgeModeHint();
    }
}

export function updateFrameRange() {
    // Update end frame based on available photos
    const totalPhotos = state.previewPhotos?.length || 0;
    const endFrameInput = document.getElementById('renderEndFrame');
    const startFrameInput = document.getElementById('renderStartFrame');

    if (endFrameInput) {
        endFrameInput.value = totalPhotos;
        endFrameInput.max = totalPhotos;
    }
    if (startFrameInput) {
        startFrameInput.max = totalPhotos;
    }

    // Update frame count display
    const frameCount = document.getElementById('renderFrameCount');
    if (frameCount) {
        frameCount.textContent = `${totalPhotos} photos available`;
    }
}

async function startRender() {
    const config = {
        output_folder: 'out',
        filename: document.getElementById('renderFilename').value || 'faceflow_render',
        format: document.getElementById('renderFormat').value,
        width: parseInt(document.getElementById('renderWidth').value) || 1920,
        height: parseInt(document.getElementById('renderHeight').value) || 1080,
        frame_duration_ms: parseInt(document.getElementById('renderFrameDuration').value) || 200,
        target_face_width: parseInt(document.getElementById('renderFaceWidth').value) || 150,
        angle_offset: parseFloat(document.getElementById('renderAngle').value) || 0,
        do_scale: document.getElementById('renderScale').checked,
        do_rotate: document.getElementById('renderRotate').checked,
        age_mode: document.getElementById('renderAgeMode').value,
        blur_amount: parseInt(document.getElementById('renderBlur').value) || 0,
        start_frame: parseInt(document.getElementById('renderStartFrame').value) || 1,
        end_frame: parseInt(document.getElementById('renderEndFrame').value) || state.previewPhotos.length,
        birth_date: state.birthDate
    };

    try {
        const response = await fetch('/api/render', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });

        const result = await response.json();

        if (response.ok) {
            // Show progress section, hide complete section
            document.getElementById('renderSettings').classList.add('rendering');
            document.getElementById('renderProgress').classList.remove('hidden');
            document.getElementById('renderComplete').classList.add('hidden');
            document.getElementById('startRenderBtn').disabled = true;

            // Scroll to top of render content
            document.getElementById('render-content').scrollTop = 0;

            // Start polling for status
            startStatusPolling();
        } else {
            showToast('Failed to start render: ' + (result.error || 'Unknown error'), 'error');
        }
    } catch (err) {
        showToast('Server error: ' + err.message, 'error');
    }
}

async function cancelRender() {
    try {
        const response = await fetch('/api/render-cancel', {
            method: 'POST'
        });

        if (!response.ok) {
            const result = await response.json();
            console.error('Cancel failed:', result.error);
        }
    } catch (err) {
        console.error('Cancel error:', err);
    }
}

async function openOutputFolder() {
    try {
        await fetch('/api/open-folder?type=out');
    } catch (err) {
        console.error('Failed to open output folder:', err);
    }
}

async function openRenderedVideo() {
    if (!lastOutputPath) return;

    try {
        await fetch(`/api/open-file?path=${encodeURIComponent(lastOutputPath)}`);
    } catch (err) {
        console.error('Failed to open video:', err);
    }
}

async function openOverlayVideo() {
    if (!lastOverlayPath) return;

    try {
        await fetch(`/api/open-file?path=${encodeURIComponent(lastOverlayPath)}`);
    } catch (err) {
        console.error('Failed to open overlay video:', err);
    }
}

function startStatusPolling() {
    // Clear any existing interval
    if (renderPollInterval) {
        clearInterval(renderPollInterval);
    }

    // Poll immediately and then every 300ms
    pollRenderStatus();
    renderPollInterval = setInterval(pollRenderStatus, 300);
}

async function pollRenderStatus() {
    try {
        const [statusRes, logRes] = await Promise.all([
            fetch('/api/render-status'),
            fetch('/api/render-log')
        ]);

        const status = await statusRes.json();
        const logData = await logRes.json();

        // Update progress bar
        const progressBar = document.getElementById('renderProgressBar');
        const progressText = document.getElementById('renderProgressText');
        const frameCounter = document.getElementById('renderFrameCounter');

        progressBar.style.width = `${status.progress}%`;
        progressText.textContent = `${status.progress}%`;
        frameCounter.textContent = `Frame ${status.current_frame} / ${status.total_frames}`;

        // Update log
        const logOutput = document.getElementById('renderLog');
        logOutput.textContent = logData.log || '';
        logOutput.scrollTop = logOutput.scrollHeight;

        // Check if complete
        if (!status.running) {
            clearInterval(renderPollInterval);
            renderPollInterval = null;

            // Update UI
            document.getElementById('startRenderBtn').disabled = false;

            if (status.status === 'complete') {
                progressText.textContent = 'Complete!';
                lastOutputPath = status.output_path;
                lastOverlayPath = status.overlay_path;
                lastAgeMode = status.age_mode;

                // Hide progress, show complete section
                document.getElementById('renderProgress').classList.add('hidden');
                document.getElementById('renderComplete').classList.remove('hidden');

                // Show output path in complete section
                const outputInfo = document.getElementById('renderOutputInfo');
                outputInfo.textContent = status.output_path;

                // Show/hide buttons based on age mode
                const videoBtn = document.getElementById('openVideoBtn');
                const overlayBtn = document.getElementById('openOverlayBtn');

                if (status.age_mode === 'overlay_only') {
                    // Only overlay was generated
                    videoBtn.classList.add('hidden');
                    overlayBtn.classList.remove('hidden');
                    overlayBtn.textContent = 'View Overlay Video';
                } else if (status.age_mode === 'separate') {
                    // Both video and overlay were generated
                    videoBtn.classList.remove('hidden');
                    overlayBtn.classList.remove('hidden');
                    outputInfo.textContent = `Video: ${status.output_path}\nOverlay: ${status.overlay_path}`;
                } else {
                    // Normal video only
                    videoBtn.classList.remove('hidden');
                    overlayBtn.classList.add('hidden');
                }
            } else if (status.status === 'cancelled') {
                progressText.textContent = 'Cancelled';
            } else if (status.status === 'error') {
                progressText.textContent = 'Error';
                showToast('Render failed: ' + (status.error || 'Unknown error'), 'error');
            }

            // Allow starting a new render after a delay
            setTimeout(() => {
                document.getElementById('renderSettings').classList.remove('rendering');
            }, 2000);
        }
    } catch (err) {
        console.error('Status poll error:', err);
    }
}
