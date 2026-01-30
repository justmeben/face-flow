// ============ Status Page ============
// Status display, folder management, and scan functionality

import { state } from './state.js';
import { migrateFaceData, getSubjectData } from './utils.js';
import { loadPreviewPhoto } from './preview.js';

export function setupStatusPage() {
    document.getElementById('openPhotosBtn').addEventListener('click', () => openFolder('photos'));
    document.getElementById('openReferenceBtn').addEventListener('click', () => openFolder('reference'));
    document.getElementById('openDataBtn').addEventListener('click', () => openFolder('data'));
    document.getElementById('scanBtn').addEventListener('click', runScan);
    document.getElementById('scanBtnMain').addEventListener('click', runScan);
    document.getElementById('refreshStatusBtn').addEventListener('click', refreshStatus);

    // Welcome section collapse toggle
    const welcomeSection = document.getElementById('welcomeSection');
    const welcomeToggle = document.getElementById('welcomeToggle');

    // Restore state from localStorage
    if (localStorage.getItem('welcomeCollapsed') === 'true') {
        welcomeSection.classList.add('collapsed');
    }

    welcomeToggle.addEventListener('click', () => {
        welcomeSection.classList.toggle('collapsed');
        localStorage.setItem('welcomeCollapsed', welcomeSection.classList.contains('collapsed'));
    });
}

export async function refreshStatus() {
    try {
        const response = await fetch('/api/status');
        if (response.ok) {
            const status = await response.json();
            document.getElementById('statusPhotosCount').textContent = status.photos_count;
            document.getElementById('statusReferenceCount').textContent = status.reference_count;
            document.getElementById('statusProcessedCount').textContent = status.processed_count;
            document.getElementById('statusDetectedCount').textContent = status.subject_detected_count;
            document.getElementById('statusUnprocessedCount').textContent = status.unprocessed_count;
        }
    } catch (e) {
        console.error('Failed to refresh status:', e);
    }
}

async function openFolder(type) {
    try {
        await fetch(`/api/open-folder?type=${type}`);
    } catch (e) {
        console.error('Failed to open folder:', e);
    }
}

function setScanButtonsState(disabled, text) {
    const scanBtn = document.getElementById('scanBtn');
    const scanBtnMain = document.getElementById('scanBtnMain');
    const scanBtnMainText = document.getElementById('scanBtnMainText');
    const spinner = document.getElementById('scanSpinner');

    scanBtn.disabled = disabled;
    scanBtn.textContent = text;
    scanBtnMain.disabled = disabled;
    scanBtnMainText.textContent = text;

    // Show/hide spinner
    if (spinner) {
        spinner.classList.toggle('hidden', !disabled);
    }
}

async function runScan() {
    const scanLog = document.getElementById('scanLog');

    setScanButtonsState(true, 'Scanning...');
    scanLog.textContent = 'Starting face detection...\n';
    scanLog.classList.add('active');

    try {
        // Start the scan
        const response = await fetch('/api/scan', { method: 'POST' });
        const result = await response.json();

        if (response.status === 409) {
            // Scan already running
            scanLog.textContent = 'Scan already in progress...\n';
        } else if (!response.ok) {
            scanLog.textContent = `Error starting scan: ${result.error || 'Unknown error'}`;
            setScanButtonsState(false, 'Scan Photos');
            return;
        }

        // Start polling for logs
        startScanPolling();

    } catch (e) {
        scanLog.textContent = `Server error: ${e.message}\nMake sure python server.py is running.`;
        setScanButtonsState(false, 'Scan Photos');
    }
}

function startScanPolling() {
    const scanLog = document.getElementById('scanLog');

    // Poll every 300ms
    state.scanPollInterval = setInterval(async () => {
        try {
            // Get current log
            const logResponse = await fetch('/api/scan-log');
            if (logResponse.ok) {
                const logData = await logResponse.json();
                if (logData.log) {
                    scanLog.textContent = logData.log;
                    // Auto-scroll to bottom
                    scanLog.scrollTop = scanLog.scrollHeight;
                }
            }

            // Check scan status
            const statusResponse = await fetch('/api/scan-status');
            if (statusResponse.ok) {
                const status = await statusResponse.json();
                if (!status.running) {
                    // Scan finished
                    stopScanPolling();
                    onScanComplete(status);
                }
            }
        } catch (e) {
            console.error('Poll error:', e);
        }
    }, 300);
}

function stopScanPolling() {
    if (state.scanPollInterval) {
        clearInterval(state.scanPollInterval);
        state.scanPollInterval = null;
    }
}

async function onScanComplete(status) {
    const scanLog = document.getElementById('scanLog');

    // Final log fetch
    try {
        const logResponse = await fetch('/api/scan-log');
        if (logResponse.ok) {
            const logData = await logResponse.json();
            scanLog.textContent = logData.log || 'Scan completed.';
            if (!status.success) {
                scanLog.textContent += '\n\n[Scan completed with errors]';
            }
        }
    } catch (e) {
        // Ignore
    }

    await refreshStatus();

    // Reload face data
    try {
        const dataResponse = await fetch('../data/face_data.json');
        if (dataResponse.ok) {
            state.faceData = migrateFaceData(await dataResponse.json());
            state.birthDate = state.faceData.birthDate || state.birthDate;
            document.getElementById('birthDateInput').value = state.birthDate;
            state.allPhotos = state.faceData.photos || [];
            state.previewPhotos = state.allPhotos.filter(p => getSubjectData(p)?.detected === true);
            state.previewPhotos.sort((a, b) => (a.metadata?.date_taken || '').localeCompare(b.metadata?.date_taken || ''));

            if (state.previewPhotos.length > 0 && !state.previewPhoto) {
                loadPreviewPhoto(0);
            }
        }
    } catch (e) {
        console.error('Failed to reload face data:', e);
    }

    setScanButtonsState(false, 'Scan Photos');
}
