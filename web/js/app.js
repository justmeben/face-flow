// ============ Main Entry Point ============
// Initialization and wiring up all modules

import { state } from './state.js';
import { migrateFaceData, getSubjectData, showToast } from './utils.js';
import { setupNavigation } from './navigation.js';
import { setupPreviewView, loadPreviewPhoto, renderPreviewPhoto, updatePreviewScrubber } from './preview.js';
import { setupDebugMode } from './debug.js';
import { setupEditMode } from './editor.js';
import { setupStatusPage } from './status.js';
import { setupRenderPage, updateFrameRange, syncFromPreview } from './render.js';

async function init() {
    try {
        // Load face data
        const response = await fetch('../data/face_data.json');
        if (!response.ok) throw new Error('Could not load face_data.json');
        state.faceData = await response.json();

        // Migrate old "ben" key to "subject"
        state.faceData = migrateFaceData(state.faceData);

        // Get birth date from data
        state.birthDate = state.faceData.birthDate || '1996-02-07';
        document.getElementById('birthDateInput').value = state.birthDate;

        state.allPhotos = state.faceData.photos || [];

        // Filter for preview view - only photos with subject detected
        state.previewPhotos = state.allPhotos.filter(p => getSubjectData(p)?.detected === true);
        state.previewPhotos.sort((a, b) => (a.metadata?.date_taken || '').localeCompare(b.metadata?.date_taken || ''));

        setupNavigation();
        setupPreviewView();
        setupStatusPage();
        setupRenderPage();
        setupDebugMode();
        setupEditMode();
        setupBirthDateEditor();

        // Update render frame range and sync settings after photos are loaded
        updateFrameRange();
        syncFromPreview();

        // Load first photo
        if (state.previewPhotos.length > 0) loadPreviewPhoto(0);
    } catch (error) {
        console.error('Init error:', error);
    }
}

function setupBirthDateEditor() {
    document.getElementById('saveBirthDateBtn').addEventListener('click', async () => {
        const newDate = document.getElementById('birthDateInput').value;
        if (!newDate) return;

        try {
            const response = await fetch('/api/save-birthdate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ birthDate: newDate })
            });

            if (response.ok) {
                state.birthDate = newDate;
                renderPreviewPhoto();
                updatePreviewScrubber();
                showToast('Birth date saved!', 'success');
            } else {
                const result = await response.json();
                showToast('Save failed: ' + (result.error || 'Unknown error'), 'error');
            }
        } catch (err) {
            showToast('Server error - make sure python server.py is running', 'error');
        }
    });
}

// Start the application
init();
