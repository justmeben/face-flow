// ============ Navigation ============
// Page switching, keyboard navigation, and sidebar visibility

import { state } from './state.js';
import { navigatePhoto, renderPreviewPhoto } from './preview.js';
import { setEditorLandmark, exitEditMode } from './editor.js';
import { refreshStatus } from './status.js';
import { syncFromPreview } from './render.js';

export function setupNavigation() {
    // Nav item clicks
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const page = item.dataset.page;
            switchPage(page);
        });
    });

    // Keyboard navigation
    document.addEventListener('keydown', (e) => {
        if (state.editMode) {
            if (e.key === '1') setEditorLandmark('leftEye');
            else if (e.key === '2') setEditorLandmark('rightEye');
            else if (e.key === '3') setEditorLandmark('mouth');
            else if (e.key === 'Escape') exitEditMode();
            return;
        }

        if (e.key === 'ArrowLeft') navigatePhoto(-1);
        else if (e.key === 'ArrowRight') navigatePhoto(1);
    });

    // Set initial sidebar visibility
    updateSidebarVisibility();
}

export function switchPage(page) {
    state.currentPage = page;
    document.querySelectorAll('.nav-item').forEach(i => i.classList.toggle('active', i.dataset.page === page));
    document.querySelectorAll('.page').forEach(p => p.classList.toggle('active', p.id === `page-${page}`));

    updateSidebarVisibility();

    if (page === 'status') {
        refreshStatus();
    } else if (page === 'preview') {
        // Re-render to fix centering
        if (state.previewPhoto) {
            renderPreviewPhoto();
        }
    } else if (page === 'render') {
        syncFromPreview();
    }
}

export function updateSidebarVisibility() {
    // Preview page sections
    const controlsSection = document.getElementById('controlsSection');
    const toolsSection = document.getElementById('toolsSection');
    const toolsHeader = toolsSection.querySelector('h4');
    const debugModeRow = document.getElementById('debugModeRow');
    const deletePhotoRow = document.getElementById('deletePhotoRow');
    const previewFooter = document.getElementById('previewFooter');

    // Status page sections
    const foldersSection = document.getElementById('foldersSection');
    const statusActionsSection = document.getElementById('statusActionsSection');

    // Render page sections
    const renderActionsSection = document.getElementById('renderActionsSection');

    // Hide all sections first
    controlsSection.classList.add('hidden');
    toolsSection.classList.add('hidden');
    foldersSection.classList.add('hidden');
    statusActionsSection.classList.add('hidden');
    if (renderActionsSection) renderActionsSection.classList.add('hidden');
    previewFooter.classList.add('hidden');

    if (state.currentPage === 'preview') {
        previewFooter.classList.remove('hidden');

        if (state.editMode) {
            // In edit mode: show only the return button in tools
            toolsSection.classList.remove('hidden');
            toolsHeader.classList.add('hidden');
            debugModeRow.classList.add('hidden');
            deletePhotoRow.classList.add('hidden');
        } else {
            // Normal preview: show everything
            controlsSection.classList.remove('hidden');
            toolsSection.classList.remove('hidden');
            toolsHeader.classList.remove('hidden');
            debugModeRow.classList.remove('hidden');
            deletePhotoRow.classList.remove('hidden');
        }
    } else if (state.currentPage === 'status') {
        // Status page: show folders and actions
        foldersSection.classList.remove('hidden');
        statusActionsSection.classList.remove('hidden');
    } else if (state.currentPage === 'render') {
        // Render page: show render actions
        if (renderActionsSection) renderActionsSection.classList.remove('hidden');
    }
}
