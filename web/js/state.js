// ============ Centralized State ============
// All shared state is managed here for easy debugging and future enhancements

export const state = {
    // Data
    faceData: null,
    allPhotos: [],
    previewPhotos: [],
    birthDate: '1996-02-07',

    // Current page
    currentPage: 'preview',

    // Preview view state
    previewIndex: 0,
    previewImage: null,
    previewPhoto: null,
    targetFaceWidth: 150,
    isDragging: false,
    slideshowTimer: null,

    // Mode states
    debugMode: false,
    editMode: false,

    // Editor state
    editorImage: null,
    editorLandmarks: { leftEye: null, rightEye: null, mouth: null },
    currentLandmark: 'leftEye',

    // Scan state
    scanPollInterval: null
};
