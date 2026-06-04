/* ====================================================================================
   LatexGenius - Static JavaScript
   All application JavaScript consolidated from inline template scripts.
   ==================================================================================== */


/* ====================================================================================
   Section 1: Utility Functions
   Source: Multiple templates (base.html, editor.html, dashboardpage.html, etc.)
   ==================================================================================== */

/**
 * Retrieve a cookie value by name.
 * Used by all pages to get the CSRF token for AJAX requests.
 */
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

/**
 * Display a toast notification.
 * Uses the #toast-container element defined in base.html.
 * @param {string} message - The message text to display
 * @param {'success'|'error'|'info'} type - Visual type determining color and icon
 */
function toast(message, type) {
    if (!type) type = 'info';
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    const bgMap = { success: 'bg-emerald-500', error: 'bg-error', info: 'bg-primary' };
    const iconMap = { success: 'check_circle', error: 'error', info: 'info' };
    el.className = `${bgMap[type] || bgMap.info} text-white px-6 py-3 rounded-xl shadow-lg flex items-center gap-3 animate-toast`;
    el.innerHTML = `<span class="material-symbols-outlined text-xl">${iconMap[type] || iconMap.info}</span><span class="text-sm font-semibold">${message}</span>`;
    container.appendChild(el);
    setTimeout(() => {
        el.classList.add('opacity-0', 'translate-x-full');
        setTimeout(() => el.remove(), 300);
    }, 4000);
}


/* ====================================================================================
   Section 2: Theme Toggle
   Source: myapp/templates/base.html
   ==================================================================================== */

/**
 * Apply the saved or system-preferred theme on page load.
 * This runs immediately when the script loads (at end of <body>).
 */
(function applyTheme() {
    if (localStorage.getItem('theme') === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.documentElement.classList.add('dark');
    } else {
        document.documentElement.classList.remove('dark');
    }
})();

/**
 * Toggle between dark and light mode.
 * Persists the choice in localStorage.
 */
function toggleTheme() {
    if (document.documentElement.classList.contains('dark')) {
        document.documentElement.classList.remove('dark');
        localStorage.setItem('theme', 'light');
    } else {
        document.documentElement.classList.add('dark');
        localStorage.setItem('theme', 'dark');
    }
}


/* ====================================================================================
   Section 3: Drawer Controls
   Source: myapp/templates/components/drawer.html
   ==================================================================================== */

/**
 * Open the navigation drawer by adding 'open' class to panel and overlay.
 */
function openDrawer() {
    document.getElementById('drawer-panel').classList.add('open');
    document.getElementById('drawer-overlay').classList.add('open');
}

/**
 * Close the navigation drawer by removing 'open' class from panel and overlay.
 */
function closeDrawer() {
    document.getElementById('drawer-panel').classList.remove('open');
    document.getElementById('drawer-overlay').classList.remove('open');
}

/**
 * Close drawer when Escape key is pressed.
 */
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeDrawer();
    }
});


/* ====================================================================================
   Section 4: Notification Dropdown & Mark-as-Read
   Source: Multiple templates (dashboardpage.html, settings.html, notifications.html)
   ==================================================================================== */

/**
 * Toggle the notification dropdown visibility.
 */
function toggleNotificationDropdown() {
    const dropdown = document.getElementById('notification-dropdown');
    if (dropdown) dropdown.classList.toggle('hidden');
}

/**
 * Mark a single notification as read via POST request.
 * @param {string} notificationId
 */
async function markNotificationAsRead(notificationId) {
    try {
        await fetch(`/notifications/${notificationId}/read/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
    } catch (e) {
        console.error('Failed to mark notification as read:', e);
    }
}

/**
 * Close notification dropdown when clicking outside of it.
 */
document.addEventListener('click', (e) => {
    const container = document.getElementById('notification-dropdown-container');
    const dropdown = document.getElementById('notification-dropdown');
    if (container && dropdown && !container.contains(e.target)) {
        dropdown.classList.add('hidden');
    }
});


/* ====================================================================================
   Section 5: Profile Dropdown (Dashboard / Editor)
   Source: myapp/templates/pages/dashboardpage.html, myapp/templates/pages/editor.html
   ==================================================================================== */

/**
 * Toggle the profile dropdown menu.
 */
function toggleProfileDropdown() {
    const dropdown = document.getElementById('profile-dropdown');
    if (dropdown) dropdown.classList.toggle('hidden');
}

/**
 * Close profile dropdown when clicking outside of it.
 */
document.addEventListener('click', (e) => {
    const container = document.getElementById('profile-dropdown-container');
    const dropdown = document.getElementById('profile-dropdown');
    if (container && dropdown && !container.contains(e.target)) {
        dropdown.classList.add('hidden');
    }
});


/* ====================================================================================
   Section 6: Editor Functions
   Source: myapp/templates/pages/editor.html
   ==================================================================================== */

(function() {
    // Guard: only run if the editor elements exist on this page
    const editor = document.getElementById('latex-editor');
    if (!editor) return;

    const config = window.LG_CONFIG || {};
    const projectId = config.projectId;
    const statusBadge = document.getElementById('status-badge');
    const processingBadge = document.getElementById('processing-badge');
    const conversionBridge = document.getElementById('conversion-bridge');

    let undoStack = [];
    let redoStack = [];
    let isUndoing = false;
    let lastContent = editor.value;
    let previewZoom = 1.0;
    let convJobId = null;
    let convPollTimer = null;
    let currentPdfUrl = null;

    /* ---------- Undo / Redo ---------- */

    function initUndoRedo() {
        editor.addEventListener('input', () => {
            if (!isUndoing) {
                if (lastContent !== editor.value) {
                    undoStack.push(lastContent);
                    redoStack = [];
                    lastContent = editor.value;
                    updateUndoRedoButtons();
                }
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'z' && !e.shiftKey) {
                e.preventDefault();
                undoAction();
            }
            if (e.ctrlKey && e.shiftKey && e.key === 'z') {
                e.preventDefault();
                redoAction();
            }
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                saveProject();
            }
        });
    }

    function updateUndoRedoButtons() {
        document.getElementById('undo-btn').disabled = undoStack.length === 0;
        document.getElementById('redo-btn').disabled = redoStack.length === 0;
    }

    function undoAction() {
        if (undoStack.length > 0) {
            isUndoing = true;
            redoStack.push(editor.value);
            editor.value = undoStack.pop();
            lastContent = editor.value;
            isUndoing = false;
            updateUndoRedoButtons();
            toast('Undo', 'info');
        }
    }

    function redoAction() {
        if (redoStack.length > 0) {
            isUndoing = true;
            undoStack.push(editor.value);
            editor.value = redoStack.pop();
            lastContent = editor.value;
            isUndoing = false;
            updateUndoRedoButtons();
            toast('Redo', 'info');
        }
    }

    /* ---------- Editor Metadata ---------- */

    editor.addEventListener('input', () => {
        updateCursorPosition();
        calculateStats();
    });

    editor.addEventListener('click', updateCursorPosition);
    editor.addEventListener('keyup', updateCursorPosition);

    function updateCursorPosition() {
        const start = editor.selectionStart;
        const text = editor.value.substring(0, start);
        const lines = text.split('\n');
        const line = lines.length;
        const col = lines[lines.length - 1].length + 1;
        document.getElementById('cursor-position').textContent = `Ln ${line}, Col ${col}`;
    }

    function calculateStats() {
        const content = editor.value;
        let mathCount = (content.match(/\$[^\$]+\$|\\\[[^\]]+\\\]|\\\([^)]+\\\)/g) || []).length;
        let sectionCount = (content.match(/\\section\{|\\subsection\{|\\subsubsection\{/g) || []).length;
        let citationCount = (content.match(/\\cite\{|\\citep\{|\\citet\{|\\bibitem\{/g) || []).length;

        const envMatch = content.match(/\\begin\{(equation|align|gather|eqnarray)/g);
        if (envMatch) mathCount += envMatch.length;

        document.getElementById('stat-math').textContent = mathCount > 0 ? mathCount : '--';
        document.getElementById('stat-sections').textContent = sectionCount > 0 ? sectionCount : '--';
        document.getElementById('stat-citations').textContent = citationCount > 0 ? citationCount : '--';

        if (content.length > 100) {
            document.getElementById('stat-confidence').textContent = 'High';
        }
    }

    /* ---------- File & Folder ---------- */

    function toggleFolder(element, event) {
        event.stopPropagation();
        toast('Multi-file folders coming soon!', 'info');
    }

    function selectFile(filename) {
        if (filename !== 'main.tex') {
            toast('Multi-file projects coming soon!', 'info');
        }
    }

    /* ---------- Editor Modes ---------- */

    function toggleEditorMode(mode) {
        const sourceBtn = document.getElementById('mode-source');
        const visualBtn = document.getElementById('mode-visual');
        const sourcePane = document.getElementById('editor-source-pane');
        const visualPane = document.getElementById('editor-visual-pane');

        if (mode === 'source') {
            sourceBtn.classList.add('bg-white', 'dark:bg-dark-border-strong', 'shadow-sm', 'text-primary', 'dark:text-white');
            sourceBtn.classList.remove('text-slate-500', 'dark:text-dark-text-muted');
            visualBtn.classList.remove('bg-white', 'dark:bg-dark-border-strong', 'shadow-sm', 'text-primary', 'dark:text-white');
            visualBtn.classList.add('text-slate-500', 'dark:text-dark-text-muted');
            sourcePane.classList.remove('hidden');
            visualPane.classList.add('hidden');
        } else {
            visualBtn.classList.add('bg-white', 'dark:bg-dark-border-strong', 'shadow-sm', 'text-primary', 'dark:text-white');
            visualBtn.classList.remove('text-slate-500', 'dark:text-dark-text-muted');
            sourceBtn.classList.remove('bg-white', 'dark:bg-dark-border-strong', 'shadow-sm', 'text-primary', 'dark:text-white');
            sourceBtn.classList.add('text-slate-500', 'dark:text-dark-text-muted');
            sourcePane.classList.add('hidden');
            visualPane.classList.remove('hidden');
        }
    }

    /* ---------- Preview ---------- */

    function zoomPreview(factor) {
        const iframe = document.getElementById('preview-iframe');
        previewZoom = Math.max(0.25, Math.min(3.0, previewZoom * factor));
        iframe.style.transform = `scale(${previewZoom})`;
    }

    function toggleEditorFullscreen() {
        const pane = document.getElementById('editor-source-pane');
        if (!document.fullscreenElement) {
            pane.requestFullscreen().catch(() => {
                toast('Fullscreen not supported', 'error');
            });
        } else {
            document.exitFullscreen();
        }
    }

    function togglePreviewFullscreen() {
        const container = document.getElementById('preview-container');
        if (!document.fullscreenElement) {
            container.requestFullscreen().catch(() => {
                toast('Fullscreen not supported', 'error');
            });
        } else {
            document.exitFullscreen();
        }
    }

    /* ---------- Share Modal ---------- */

    function openShareModal() {
        const overlay = document.getElementById('share-modal-overlay');
        overlay.classList.remove('hidden');
        overlay.classList.add('flex');
        document.body.style.overflow = 'hidden';
        loadShareData();
    }

    function closeShareModal() {
        const overlay = document.getElementById('share-modal-overlay');
        overlay.classList.add('hidden');
        overlay.classList.remove('flex');
        document.body.style.overflow = '';
    }

    async function loadShareData() {
        const invitationsList = document.getElementById('pending-invitations');
        const collaboratorsList = document.getElementById('collaborators-list');

        try {
            const response = await fetch(`/editor/${projectId}/share/`);
            const data = await response.json();

            if (data.status === 'success') {
                if (data.invitations && data.invitations.length > 0) {
                    invitationsList.innerHTML = data.invitations.map(inv => `
                        <div class="flex items-center justify-between p-3 bg-surface dark:bg-dark-surface-alt rounded-lg">
                            <div class="flex items-center gap-3">
                                <div class="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center">
                                    <span class="material-symbols-outlined text-sm text-primary">mail</span>
                                </div>
                                <div>
                                    <p class="text-sm font-medium dark:text-white">${inv.email}</p>
                                    <p class="text-xs text-slate-400">${inv.permission} &bull; ${inv.status}</p>
                                </div>
                            </div>
                            ${inv.status === 'pending' ? `<button onclick="revokeInvitation('${inv.id}')" class="text-xs text-error hover:underline">Revoke</button>` : ''}
                        </div>
                    `).join('');
                }

                if (data.collaborators && data.collaborators.length > 0) {
                    collaboratorsList.innerHTML = data.collaborators.map(collab => `
                        <div class="flex items-center justify-between p-3 bg-surface dark:bg-dark-surface-alt rounded-lg">
                            <div class="flex items-center gap-3">
                                <div class="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center">
                                    <span class="material-symbols-outlined text-sm text-primary">person</span>
                                </div>
                                <div>
                                    <p class="text-sm font-medium dark:text-white">${collab.name}</p>
                                    <p class="text-xs text-slate-400">${collab.email}</p>
                                </div>
                            </div>
                            <button onclick="removeCollaborator('${collab.id}')" class="text-xs text-error hover:underline">Remove</button>
                        </div>
                    `).join('');
                }
            }
        } catch (e) {
            console.log('Share data not available');
        }
    }

    async function sendShareInvitation() {
        const email = document.getElementById('share-email').value.trim();
        const permission = document.getElementById('share-permission').value;

        if (!email) {
            toast('Please enter an email', 'error');
            return;
        }

        try {
            const response = await fetch(`/editor/${projectId}/share/create/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: JSON.stringify({ email: email, permission: permission })
            });

            const data = await response.json();

            if (data.status === 'success') {
                toast('Invitation sent!', 'success');
                document.getElementById('share-email').value = '';
                loadShareData();
            } else {
                toast(data.message || 'Failed to send invitation', 'error');
            }
        } catch (e) {
            toast('Project sharing is a Pro feature. Upgrade to collaborate.', 'info');
        }
    }

    /* ---------- History / Versions Modal ---------- */

    function openHistoryModal() {
        const overlay = document.getElementById('history-modal-overlay');
        overlay.classList.remove('hidden');
        overlay.classList.add('flex');
        document.body.style.overflow = 'hidden';
        loadVersions();
    }

    function closeHistoryModal() {
        const overlay = document.getElementById('history-modal-overlay');
        overlay.classList.add('hidden');
        overlay.classList.remove('flex');
        document.body.style.overflow = '';
    }

    async function loadVersions() {
        const versionsList = document.getElementById('versions-list');

        try {
            const response = await fetch(`/editor/${projectId}/versions/`);
            const data = await response.json();

            if (data.status === 'success' && data.versions && data.versions.length > 0) {
                versionsList.innerHTML = data.versions.map(version => `
                    <div class="flex items-start justify-between p-4 bg-surface dark:bg-dark-surface-alt rounded-lg hover:bg-surface-variant dark:hover:bg-dark-border-strong transition-colors">
                        <div class="flex items-start gap-3">
                            <div class="w-10 h-10 rounded-lg bg-primary/10 dark:bg-primary/20 flex items-center justify-center flex-shrink-0">
                                <span class="material-symbols-outlined text-primary">history</span>
                            </div>
                            <div>
                                <p class="text-sm font-medium dark:text-white">Version ${version.version}</p>
                                <p class="text-xs text-slate-400 dark:text-dark-text-muted mt-0.5">${version.message || 'Auto-saved'}</p>
                                <p class="text-xs text-slate-400 dark:text-dark-text-muted mt-1">${new Date(version.created_at).toLocaleString()}</p>
                            </div>
                        </div>
                        <button onclick="restoreVersion(${version.version})" class="px-3 py-1.5 text-xs text-primary border border-primary/30 rounded-lg hover:bg-primary/5 transition-colors">
                            Restore
                        </button>
                    </div>
                `).join('');
            } else {
                versionsList.innerHTML = `
                    <div class="text-center py-8">
                        <span class="material-symbols-outlined text-5xl text-slate-300 dark:text-dark-border-strong mb-4 block">history</span>
                        <p class="text-sm font-medium text-slate-600 dark:text-dark-text-muted mb-1">No versions yet</p>
                        <p class="text-xs text-slate-400 dark:text-dark-text-muted">Save your project to create version history.</p>
                    </div>
                `;
            }
        } catch (e) {
            versionsList.innerHTML = `
                <div class="text-center py-8">
                    <span class="material-symbols-outlined text-5xl text-slate-300 dark:text-dark-border-strong mb-4 block">info</span>
                    <p class="text-sm font-medium text-slate-600 dark:text-dark-text-muted mb-1">Version History is a Pro feature</p>
                    <p class="text-xs text-slate-400 dark:text-dark-text-muted">Upgrade to access previous versions of your documents.</p>
                </div>
            `;
        }
    }

    async function restoreVersion(versionNumber) {
        if (!confirm(`Restore to version ${versionNumber}? Current changes will be saved first.`)) {
            return;
        }

        try {
            const response = await fetch(`/editor/${projectId}/versions/${versionNumber}/restore/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                }
            });

            const data = await response.json();

            if (data.status === 'success') {
                editor.value = data.content;
                lastContent = data.content;
                undoStack = [];
                redoStack = [];
                updateUndoRedoButtons();
                toast(`Restored to version ${versionNumber}`, 'success');
                closeHistoryModal();
            } else {
                toast('Failed to restore version', 'error');
            }
        } catch (e) {
            toast('Version restore is a Pro feature', 'info');
        }
    }

    /* ---------- New File / Folder Modals ---------- */

    function showNewFileModal() {
        const overlay = document.getElementById('new-file-modal-overlay');
        overlay.classList.remove('hidden');
        overlay.classList.add('flex');
        document.body.style.overflow = 'hidden';
    }

    function closeNewFileModal() {
        const overlay = document.getElementById('new-file-modal-overlay');
        overlay.classList.add('hidden');
        overlay.classList.remove('flex');
        document.body.style.overflow = '';
    }

    function createNewFile() {
        toast('Multi-file projects coming soon!', 'info');
        closeNewFileModal();
    }

    function showNewFolderModal() {
        const overlay = document.getElementById('new-folder-modal-overlay');
        overlay.classList.remove('hidden');
        overlay.classList.add('flex');
        document.body.style.overflow = 'hidden';
    }

    function closeNewFolderModal() {
        const overlay = document.getElementById('new-folder-modal-overlay');
        overlay.classList.add('hidden');
        overlay.classList.remove('flex');
        document.body.style.overflow = '';
    }

    function createNewFolder() {
        toast('Multi-file projects coming soon!', 'info');
        closeNewFolderModal();
    }

    /* ---------- Re-Process Modal ---------- */

    function openReprocessModal() {
        const overlay = document.getElementById('reprocess-modal-overlay');
        overlay.classList.remove('hidden');
        overlay.classList.add('flex');
        document.body.style.overflow = 'hidden';
    }

    function closeReprocessModal() {
        const overlay = document.getElementById('reprocess-modal-overlay');
        overlay.classList.add('hidden');
        overlay.classList.remove('flex');
        document.body.style.overflow = '';
    }

    /* ---------- Conversion Overlay ---------- */

    function showConversionOverlay() {
        document.getElementById('conversion-overlay').classList.remove('hidden');
        document.getElementById('conversion-overlay').classList.add('flex');
    }

    function hideConversionOverlay() {
        document.getElementById('conversion-overlay').classList.add('hidden');
        document.getElementById('conversion-overlay').classList.remove('flex');
        if (convPollTimer) { clearInterval(convPollTimer); convPollTimer = null; }
    }

    function updateConvOverlay(data) {
        document.getElementById('conv-bar').style.width = data.progress_percent + '%';
        document.getElementById('conv-pct').textContent = data.progress_percent + '%';
        document.getElementById('conv-message').textContent = data.progress_message;
    }

    function pollConversionStatus() {
        if (!convJobId) return;
        fetch(`/convert/${projectId}/status/`)
            .then(r => r.json())
            .then(data => {
                updateConvOverlay(data);
                if (data.status === 'completed') {
                    document.getElementById('conv-spinner').classList.add('hidden');
                    document.getElementById('conv-success').classList.remove('hidden');
                    document.getElementById('conv-title').textContent = 'Conversion Complete!';
                    document.getElementById('conv-message').textContent = 'Loading result...';
                    clearInterval(convPollTimer);
                    convPollTimer = null;
                    fetchEditorContent();
                } else if (data.status === 'failed') {
                    document.getElementById('conv-spinner').classList.add('hidden');
                    document.getElementById('conv-error').classList.remove('hidden');
                    document.getElementById('conv-title').textContent = 'Conversion Failed';
                    document.getElementById('conv-message').textContent = data.error_message || data.progress_message;
                    document.getElementById('conv-bar').classList.remove('bg-primary');
                    document.getElementById('conv-bar').classList.add('bg-error');
                    clearInterval(convPollTimer);
                    convPollTimer = null;
                }
            })
            .catch(() => {});
    }

    async function fetchEditorContent() {
        window.location.href = `/editor/${projectId}/?autocompile=true`;
    }

    async function reprocessDocument() {
        const fileInput = document.getElementById('reprocess-file');
        const note = document.getElementById('reprocess-note').value;

        if (!fileInput.files.length) {
            toast('Please select a document to re-process', 'error');
            return;
        }

        const file = fileInput.files[0];
        const formData = new FormData();
        formData.append('document', file);
        if (note) formData.append('note', note);

        const csrftoken = getCookie('csrftoken');

        try {
            const response = await fetch(`/editor/${projectId}/reprocess/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrftoken },
                body: formData
            });

            const data = await response.json();

            if (data.status === 'started') {
                convJobId = data.job_id;
                closeReprocessModal();
                showConversionOverlay();
                convPollTimer = setInterval(pollConversionStatus, 2000);
                pollConversionStatus();
            } else {
                toast(data.message || 'AI re-processing failed. Please try again.', 'error');
            }
        } catch (e) {
            toast('Network error. Please try again.', 'error');
        }
    }

    /* ---------- Fetch with Retry ---------- */

    async function fetchWithRetry(url, options = {}, retries = 3, backoff = 1000) {
        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                if (response.status >= 500 && retries > 0) {
                    throw new Error(`Server error: ${response.status}`);
                }
                return response;
            }
            return response;
        } catch (error) {
            if (retries > 0) {
                console.warn(`Retrying fetch... (${retries} retries left)`);
                await new Promise(resolve => setTimeout(resolve, backoff));
                return fetchWithRetry(url, options, retries - 1, backoff * 2);
            }
            throw error;
        }
    }

    /* ---------- Save Project ---------- */

    async function saveProject() {
        const saveBtn = document.getElementById('save-button');
        const originalHtml = saveBtn.innerHTML;
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<span class="material-symbols-outlined animate-spin text-sm">sync</span> Saving...';

        try {
            const response = await fetchWithRetry(`/editor/${projectId}/save/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({ content: editor.value })
            });

            if (response.ok) {
                statusBadge.className = "w-1.5 h-1.5 rounded-full bg-emerald-500";
                toast('Project saved successfully', 'success');

                try {
                    const csrftoken = getCookie('csrftoken');
                    await fetch(`/editor/${projectId}/versions/create/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrftoken
                        },
                        body: JSON.stringify({ content: editor.value, message: 'Auto-save' })
                    });
                } catch (e) {
                    console.log('Version tracking not available');
                }

                return true;
            } else {
                const data = await response.json().catch(() => ({}));
                toast(data.message || 'Failed to save project', 'error');
                return false;
            }
        } catch (error) {
            console.error('Save failed:', error);
            toast('Network error while saving. Please check your connection.', 'error');
            return false;
        } finally {
            saveBtn.disabled = false;
            saveBtn.innerHTML = originalHtml;
        }
    }

    /* ---------- Compile & Preview ---------- */

    function togglePreviewMode(mode) {
        const pdfIframe = document.getElementById('preview-iframe');
        const logView = document.getElementById('preview-log');
        const pdfBtn = document.getElementById('mode-pdf');
        const logBtn = document.getElementById('mode-log');

        if (mode === 'pdf') {
            pdfIframe.classList.remove('hidden');
            logView.classList.add('hidden');
            pdfBtn.classList.add('text-primary');
            pdfBtn.classList.remove('text-slate-600', 'dark:text-dark-text-muted');
            pdfBtn.classList.add('dark:text-white');
            logBtn.classList.remove('text-primary', 'dark:text-white');
            logBtn.classList.add('text-slate-600', 'dark:text-dark-text-muted');
        } else {
            pdfIframe.classList.add('hidden');
            logView.classList.remove('hidden');
            pdfBtn.classList.remove('text-primary', 'dark:text-white');
            pdfBtn.classList.add('text-slate-600', 'dark:text-dark-text-muted');
            logBtn.classList.add('text-primary', 'dark:text-white');
            logBtn.classList.remove('text-slate-600', 'dark:text-dark-text-muted');
        }
    }

    async function compileProject() {
        const compileBtn = document.getElementById('compile-button');
        const originalHtml = compileBtn.innerHTML;
        const loadingOverlay = document.getElementById('preview-loading');
        const placeholder = document.getElementById('preview-placeholder');
        const pdfIframe = document.getElementById('preview-iframe');
        const logView = document.getElementById('preview-log');
        const downloadBtn = document.getElementById('download-pdf-btn');

        const saved = await saveProject();
        if (!saved) {
            toast('Auto-save failed. Compilation aborted.', 'error');
            return;
        }

        compileBtn.disabled = true;
        compileBtn.innerHTML = '<span class="material-symbols-outlined animate-spin text-sm">sync</span> Compiling...';
        loadingOverlay.classList.remove('hidden');
        processingBadge.classList.remove('hidden');
        processingBadge.classList.add('flex');

        toast('Starting compilation...', 'info');

        try {
            const response = await fetch(`/editor/${projectId}/compile/`);

            if (response.ok) {
                const blob = await response.blob();

                if (currentPdfUrl) {
                    window.URL.revokeObjectURL(currentPdfUrl);
                }

                currentPdfUrl = window.URL.createObjectURL(blob);
                pdfIframe.src = currentPdfUrl;
                previewZoom = 1.0;
                pdfIframe.style.transform = 'scale(1)';

                placeholder.classList.add('hidden');
                downloadBtn.classList.remove('hidden');
                conversionBridge.classList.remove('hidden');
                conversionBridge.classList.add('flex');
                togglePreviewMode('pdf');

                statusBadge.className = "w-1.5 h-1.5 rounded-full bg-emerald-500";
                toast('Compilation successful', 'success');
            } else {
                const text = await response.text();
                logView.textContent = text;

                placeholder.classList.add('hidden');
                togglePreviewMode('log');

                statusBadge.className = "w-1.5 h-1.5 rounded-full bg-error";
                toast('Compilation failed. Check logs.', 'error');
            }
        } catch (error) {
            console.error('Compilation error:', error);
            toast('Compilation error: ' + error.message, 'error');
            statusBadge.className = "w-1.5 h-1.5 rounded-full bg-error";
        } finally {
            compileBtn.disabled = false;
            compileBtn.innerHTML = originalHtml;
            loadingOverlay.classList.add('hidden');
            processingBadge.classList.add('hidden');
            processingBadge.classList.remove('flex');
        }
    }

    /* ---------- Download ---------- */

    function downloadPdf() {
        if (!currentPdfUrl) return;
        const a = document.createElement('a');
        a.href = currentPdfUrl;
        const currentTitle = document.getElementById('rename-display-editor').textContent || 'document';
        a.download = currentTitle + '.pdf';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    function downloadTex() {
        const blob = new Blob([editor.value], { type: 'text/x-tex' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'main.tex';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
    }

    function copyToClipboard() {
        navigator.clipboard.writeText(editor.value);
        toast('LaTeX code copied to clipboard!', 'success');
    }

    /* ---------- Rename (Editor) ---------- */

    function startRenameEditor(projectIdVal, currentTitle) {
        const display = document.getElementById('rename-display-editor');
        if (document.getElementById('rename-input-editor')) return;

        display.classList.add('hidden');

        const input = document.createElement('input');
        input.type = 'text';
        input.value = currentTitle;
        input.className = 'text-xs font-bold text-white uppercase tracking-wide bg-slate-800 border-2 border-primary rounded px-2 py-0.5 w-[200px] focus:outline-none';
        input.id = 'rename-input-editor';

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') saveRenameEditor(projectIdVal);
            if (e.key === 'Escape') cancelRenameEditor();
        });
        input.addEventListener('blur', () => saveRenameEditor(projectIdVal));

        display.parentElement.appendChild(input);
        input.focus();
        input.select();
    }

    function cancelRenameEditor() {
        const display = document.getElementById('rename-display-editor');
        const input = document.getElementById('rename-input-editor');
        if (input) input.remove();
        if (display) display.classList.remove('hidden');
    }

    async function saveRenameEditor(projectIdVal) {
        const input = document.getElementById('rename-input-editor');
        if (!input) return;

        const newTitle = input.value.trim();
        if (!newTitle) {
            cancelRenameEditor();
            return;
        }

        try {
            const response = await fetch(`/editor/${projectIdVal}/save/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({ title: newTitle })
            });

            if (response.ok) {
                document.getElementById('rename-display-editor').textContent = newTitle;
                cancelRenameEditor();
                toast('Project renamed successfully', 'success');
                document.title = newTitle + ' | LaTeXGenius';
                const sidebarTitle = document.getElementById('sidebar-project-title');
                if (sidebarTitle) sidebarTitle.textContent = newTitle + '.tex';
                const footerEditing = document.getElementById('footer-editing');
                if (footerEditing) footerEditing.textContent = 'Editing: ' + newTitle;
            } else {
                toast('Failed to rename project', 'error');
                cancelRenameEditor();
            }
        } catch (error) {
            toast('Network error while renaming', 'error');
            cancelRenameEditor();
        }
    }

    /* ---------- Modal Close on Overlay Click ---------- */

    document.getElementById('share-modal-overlay').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeShareModal();
    });

    document.getElementById('history-modal-overlay').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeHistoryModal();
    });

    document.getElementById('new-file-modal-overlay').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeNewFileModal();
    });

    document.getElementById('new-folder-modal-overlay').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeNewFolderModal();
    });

    document.getElementById('reprocess-modal-overlay').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeReprocessModal();
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeShareModal();
            closeHistoryModal();
            closeNewFileModal();
            closeNewFolderModal();
            closeReprocessModal();
        }
    });

    /* ---------- Editor Init ---------- */

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initEditor);
    } else {
        initEditor();
    }

    function initEditor() {
        initUndoRedo();
        calculateStats();

        const prefs = config.preferences || {};
        if (prefs.font_size) {
            editor.style.fontSize = prefs.font_size;
        }
        if (prefs.dark_mode === true) {
            document.documentElement.classList.add('dark');
            localStorage.setItem('theme', 'dark');
        } else if (prefs.dark_mode === false) {
            document.documentElement.classList.remove('dark');
            localStorage.setItem('theme', 'light');
        }

        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('autocompile') === 'true' || prefs.auto_compile === true) {
            setTimeout(() => {
                compileProject();
            }, 500);
        }
    }

    // Expose functions globally for onclick handlers
    window.undoAction = undoAction;
    window.redoAction = redoAction;
    window.toggleFolder = toggleFolder;
    window.selectFile = selectFile;
    window.toggleEditorMode = toggleEditorMode;
    window.zoomPreview = zoomPreview;
    window.toggleEditorFullscreen = toggleEditorFullscreen;
    window.togglePreviewFullscreen = togglePreviewFullscreen;
    window.openShareModal = openShareModal;
    window.closeShareModal = closeShareModal;
    window.sendShareInvitation = sendShareInvitation;
    window.openHistoryModal = openHistoryModal;
    window.closeHistoryModal = closeHistoryModal;
    window.restoreVersion = restoreVersion;
    window.showNewFileModal = showNewFileModal;
    window.closeNewFileModal = closeNewFileModal;
    window.createNewFile = createNewFile;
    window.showNewFolderModal = showNewFolderModal;
    window.closeNewFolderModal = closeNewFolderModal;
    window.createNewFolder = createNewFolder;
    window.openReprocessModal = openReprocessModal;
    window.closeReprocessModal = closeReprocessModal;
    window.showConversionOverlay = showConversionOverlay;
    window.hideConversionOverlay = hideConversionOverlay;
    window.reprocessDocument = reprocessDocument;
    window.saveProject = saveProject;
    window.togglePreviewMode = togglePreviewMode;
    window.compileProject = compileProject;
    window.downloadPdf = downloadPdf;
    window.downloadTex = downloadTex;
    window.copyToClipboard = copyToClipboard;
    window.startRenameEditor = startRenameEditor;
    window.cancelRenameEditor = cancelRenameEditor;
    window.saveRenameEditor = saveRenameEditor;
})();


/* ====================================================================================
   Section 7: Dashboard Functions
   Source: myapp/templates/pages/dashboardpage.html
   ==================================================================================== */

(function() {
    // Guard: only run on dashboard page
    const aiConvertOverlay = document.getElementById('ai-convert-modal-overlay');
    if (!aiConvertOverlay) return;

    let currentRenameId = null;

    function openAIConvertModal() {
        aiConvertOverlay.classList.remove('hidden');
        aiConvertOverlay.classList.add('flex');
        document.body.style.overflow = 'hidden';
    }

    function closeAIConvertModal() {
        aiConvertOverlay.classList.add('hidden');
        aiConvertOverlay.classList.remove('flex');
        document.body.style.overflow = '';
    }

    aiConvertOverlay.addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeAIConvertModal();
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeAIConvertModal();
    });

    function updateFileName(input) {
        const display = document.getElementById('fileNameDisplay');
        if (input.files && input.files[0]) {
            display.textContent = `Selected: ${input.files[0].name}`;
            display.classList.remove('hidden');
        } else {
            display.classList.add('hidden');
        }
    }

    /* ---------- Dashboard Rename ---------- */

    function startRename(projectId, currentTitle) {
        if (currentRenameId) cancelRename();
        currentRenameId = projectId;

        const display = document.getElementById(`rename-display-${projectId}`);
        const container = display.parentElement;

        display.classList.add('hidden');

        const input = document.createElement('input');
        input.type = 'text';
        input.value = currentTitle;
        input.className = 'text-sm font-semibold px-2 py-1 border-2 border-primary rounded w-full focus:outline-none dark:bg-dark-surface-alt dark:text-white';
        input.id = `rename-input-${projectId}`;

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') saveRename(projectId);
            if (e.key === 'Escape') cancelRename();
        });
        input.addEventListener('blur', () => saveRename(projectId));

        container.appendChild(input);
        input.focus();
        input.select();
    }

    function cancelRename() {
        if (!currentRenameId) return;
        const display = document.getElementById(`rename-display-${currentRenameId}`);
        const input = document.getElementById(`rename-input-${currentRenameId}`);
        if (input) input.remove();
        if (display) display.classList.remove('hidden');
        currentRenameId = null;
    }

    async function saveRename(projectId) {
        const input = document.getElementById(`rename-input-${projectId}`);
        if (!input) return;

        const newTitle = input.value.trim();
        if (!newTitle) {
            cancelRename();
            return;
        }

        try {
            const response = await fetch(`/editor/${projectId}/save/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({ title: newTitle })
            });

            if (response.ok) {
                const display = document.getElementById(`rename-display-${projectId}`);
                display.textContent = newTitle;
                cancelRename();
                toast('Project renamed successfully', 'success');
            } else {
                toast('Failed to rename project', 'error');
                cancelRename();
            }
        } catch (error) {
            toast('Network error while renaming', 'error');
            cancelRename();
        }
    }

    /* ---------- Delete Project ---------- */

    async function deleteProject(projectId, projectTitle) {
        if (!confirm(`Delete "${projectTitle}"? This action cannot be undone.`)) return;

        try {
            const response = await fetch(`/editor/${projectId}/delete/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!response.ok) {
                const text = await response.text();
                console.error('Delete failed:', response.status, text);
                toast('Failed to delete project (server error)', 'error');
                return;
            }

            const data = await response.json();

            if (data.status === 'success') {
                const projectDiv = document.getElementById(`project-row-${projectId}`);
                if (projectDiv) {
                    projectDiv.remove();
                } else {
                    location.reload();
                }
                toast('Project deleted', 'success');
            } else {
                toast(data.message || 'Failed to delete project', 'error');
            }
        } catch (e) {
            console.error('Delete error:', e);
            toast('Network error while deleting project', 'error');
        }
    }

    // Expose dashboard functions globally
    window.openAIConvertModal = openAIConvertModal;
    window.closeAIConvertModal = closeAIConvertModal;
    window.updateFileName = updateFileName;
    window.startRename = startRename;
    window.cancelRename = cancelRename;
    window.saveRename = saveRename;
    window.deleteProject = deleteProject;
})();


/* ====================================================================================
   Section 8: Settings Functions
   Source: myapp/templates/pages/settings.html
   ==================================================================================== */

(function() {
    const featureBtn = document.querySelector('[onclick*="showFeatureComingSoon"]');
    if (!featureBtn) return;

    function showFeatureComingSoon(featureName) {
        toast(`${featureName} is coming soon!`, 'info');
    }

    async function savePreference(key, value) {
        const config = window.LG_CONFIG || {};

        try {
            const csrftoken = getCookie('csrftoken');
            const response = await fetch(config.savePreferencesUrl || '/preferences/save/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrftoken,
                },
                body: `${key}=${value}`
            });

            if (!response.ok) {
                toast('Failed to save preference', 'error');
                return;
            }

            const data = await response.json();

            if (data.status === 'success') {
                toast('Preference saved', 'success');

                if (key === 'dark_mode') {
                    if (value) {
                        document.documentElement.classList.add('dark');
                        localStorage.setItem('theme', 'dark');
                    } else {
                        document.documentElement.classList.remove('dark');
                        localStorage.setItem('theme', 'light');
                    }
                }
            } else {
                toast('Failed to save preference', 'error');
            }
        } catch (error) {
            toast('Network error', 'error');
        }
    }

    window.showFeatureComingSoon = showFeatureComingSoon;
    window.savePreference = savePreference;
})();


/* ====================================================================================
   Section 9: Pricing Page Functions
   Source: myapp/templates/pages/pricing.html
   ==================================================================================== */

(function() {
    const monthlyBtn = document.getElementById('monthly-btn');
    if (!monthlyBtn) return;

    let billingInterval = 'monthly';

    monthlyBtn.addEventListener('click', () => {
        billingInterval = 'monthly';
        monthlyBtn.className = 'px-6 py-2.5 rounded-lg text-sm font-semibold bg-primary text-white transition-all';
        const yearlyBtn = document.getElementById('yearly-btn');
        yearlyBtn.className = 'px-6 py-2.5 rounded-lg text-sm font-semibold text-secondary dark:text-secondary-dark transition-all';
        document.querySelectorAll('.price-number').forEach(el => {
            el.textContent = el.dataset.plan === 'Free' ? 'Free' : '$' + el.dataset.monthly;
        });
    });

    document.getElementById('yearly-btn').addEventListener('click', () => {
        billingInterval = 'yearly';
        document.getElementById('yearly-btn').className = 'px-6 py-2.5 rounded-lg text-sm font-semibold bg-primary text-white transition-all';
        monthlyBtn.className = 'px-6 py-2.5 rounded-lg text-sm font-semibold text-secondary dark:text-secondary-dark transition-all';
        document.querySelectorAll('.price-number').forEach(el => {
            el.textContent = el.dataset.plan === 'Free' ? 'Free' : '$' + el.dataset.yearly;
        });
    });

    function checkout(monthlyPriceId, yearlyPriceId) {
        const config = window.LG_CONFIG || {};
        if (config.userAuthenticated) {
            const priceId = billingInterval === 'yearly' ? yearlyPriceId : monthlyPriceId;
            if (!priceId) { toast('Not available yet', 'info'); return; }
            fetch(config.createCheckoutUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': config.csrfToken },
                body: JSON.stringify({ price_id: priceId }),
            }).then(r => r.json()).then(data => {
                if (data.url) { window.location.href = data.url; }
                else { toast(data.message || 'Checkout failed', 'error'); }
            }).catch(() => toast('Network error', 'error'));
        } else {
            window.location.href = config.signupUrl;
        }
    }

    function toggleFaq(button) {
        const content = button.nextElementSibling;
        const icon = button.querySelector('.material-symbols-outlined');
        if (content.classList.contains('hidden')) {
            content.classList.remove('hidden');
            icon.style.transform = 'rotate(180deg)';
        } else {
            content.classList.add('hidden');
            icon.style.transform = 'rotate(0deg)';
        }
    }

    window.checkout = checkout;
    window.toggleFaq = toggleFaq;
})();


/* ====================================================================================
   Section 10: Upgrade Page Functions
   Source: myapp/templates/pages/upgrade.html
   ==================================================================================== */

(function() {
    const upgradeBtn = document.querySelector('[onclick*="checkout("]');
    if (!upgradeBtn) return;

    function checkout(monthlyPriceId, yearlyPriceId) {
        const config = window.LG_CONFIG || {};
        const priceId = yearlyPriceId || monthlyPriceId;
        if (!priceId) {
            toast('This plan is not available for subscription yet.', 'info');
            return;
        }
        fetch(config.createCheckoutUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': config.csrfToken,
            },
            body: JSON.stringify({ price_id: priceId }),
        })
        .then(r => r.json())
        .then(data => {
            if (data.url) {
                window.location.href = data.url;
            } else {
                toast(data.message || 'Failed to start checkout', 'error');
            }
        })
        .catch(() => toast('Network error. Please try again.', 'error'));
    }

    function toggleUpgradeFaq(button) {
        const content = button.nextElementSibling;
        const icon = button.querySelector('.material-symbols-outlined');
        if (content.classList.contains('hidden')) {
            content.classList.remove('hidden');
            icon.style.transform = 'rotate(180deg)';
        } else {
            content.classList.add('hidden');
            icon.style.transform = 'rotate(0deg)';
        }
    }

    window.checkout = checkout;
    window.toggleUpgradeFaq = toggleUpgradeFaq;
})();


/* ====================================================================================
   Section 11: Documentation Page Functions
   Source: myapp/templates/pages/documentation.html
   ==================================================================================== */

(function() {
    const sidebarToggle = document.getElementById('sidebar-toggle');
    if (!sidebarToggle) return;

    const sidebarNav = document.getElementById('sidebar-nav');

    if (sidebarToggle && sidebarNav) {
        sidebarToggle.addEventListener('click', () => {
            sidebarNav.classList.toggle('hidden');
        });
    }

    function toggleFaq(button) {
        const content = button.nextElementSibling;
        const icon = button.querySelector('.material-symbols-outlined:last-child');

        if (content.classList.contains('hidden')) {
            content.classList.remove('hidden');
            if (icon) icon.style.transform = 'rotate(180deg)';
        } else {
            content.classList.add('hidden');
            if (icon) icon.style.transform = 'rotate(0deg)';
        }
    }

    function copyCode(button) {
        const codeBlock = button.nextElementSibling.querySelector('code');
        const originalIcon = button.innerHTML;

        if (codeBlock) {
            navigator.clipboard.writeText(codeBlock.textContent).then(() => {
                button.innerHTML = '<span class="material-symbols-outlined text-green-400 text-sm">check</span>';
                setTimeout(() => {
                    button.innerHTML = originalIcon;
                }, 2000);
            });
        }
    }

    /* TOC intersection observer for active link highlighting */
    const tocLinks = document.querySelectorAll('.toc-link');
    const sections = document.querySelectorAll('section[id]');

    if (tocLinks.length && sections.length) {
        const observerOptions = {
            root: null,
            rootMargin: '-20% 0px -70% 0px',
            threshold: 0
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    tocLinks.forEach(link => {
                        link.classList.remove('bg-primary/10', 'dark:bg-primary/20', 'text-primary');
                    });

                    const activeLink = document.querySelector(`.toc-link[href="#${entry.target.id}"]`);
                    if (activeLink) {
                        activeLink.classList.add('bg-primary/10', 'dark:bg-primary/20', 'text-primary');
                    }
                }
            });
        }, observerOptions);

        sections.forEach(section => {
            observer.observe(section);
        });
    }

    window.toggleFaq = toggleFaq;
    window.copyCode = copyCode;
})();


/* ====================================================================================
   Section 12: Notifications Page Functions
   Source: myapp/templates/pages/notifications.html
   ==================================================================================== */

(function() {
    const markAllBtn = document.querySelector('[onclick*="markAllAsRead"]');
    if (!markAllBtn) return;

    async function markAsRead(notificationId) {
        await markNotificationAsRead(notificationId);
        const el = document.querySelector(`.notification-item[data-id="${notificationId}"]`);
        if (el) {
            el.classList.remove('border-l-4', 'border-l-primary');
            const btn = el.querySelector('button');
            if (btn) btn.remove();
        }
    }

    async function markAllAsRead() {
        const config = window.LG_CONFIG || {};
        try {
            const response = await fetch(config.markAllReadUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            const data = await response.json();
            if (data.status === 'success') {
                document.querySelectorAll('.notification-item').forEach(el => {
                    el.classList.remove('border-l-4', 'border-l-primary');
                    const btn = el.querySelector('button');
                    if (btn) btn.remove();
                });
                const allReadBtn = document.querySelector('[onclick*="markAllAsRead"]');
                if (allReadBtn) allReadBtn.remove();
                toast('All notifications marked as read', 'success');
            }
        } catch (e) {
            console.error('Failed to mark all as read:', e);
            toast('Failed to mark all as read', 'error');
        }
    }

    window.markAsRead = markAsRead;
    window.markAllAsRead = markAllAsRead;
})();


/* ====================================================================================
   Section 13: Conversion Page (Polling)
   Source: myapp/templates/pages/conversion.html
   ==================================================================================== */

(function() {
    const config = window.LG_CONFIG || {};
    const projectId = config.projectId;
    if (!projectId) return;

    const pollInterval = 2000;
    let pollTimer = null;

    function updateSteps(percent) {
        const steps = [
            { el: document.getElementById('step-extract'), threshold: 10 },
            { el: document.getElementById('step-analyze'), threshold: 30 },
            { el: document.getElementById('step-latex'), threshold: 50 },
            { el: document.getElementById('step-finalize'), threshold: 80 },
        ];
        steps.forEach(s => {
            if (percent >= s.threshold) markStepDone(s.el);
        });
    }

    function markStepDone(stepEl) {
        const dot = stepEl.querySelector('.step-dot');
        const icon = dot.querySelector('.material-symbols-outlined');
        dot.classList.remove('border-secondary', 'dark:border-secondary-dark');
        dot.classList.add('border-emerald-500', 'bg-emerald-50', 'dark:bg-emerald-900/20');
        icon.classList.remove('hidden');
        icon.textContent = 'check';
        icon.classList.add('text-emerald-500', 'text-xs');
        stepEl.classList.remove('text-secondary', 'dark:text-secondary-dark');
        stepEl.classList.add('text-emerald-600', 'dark:text-emerald-400');
    }

    function pollStatus() {
        fetch(`/convert/${projectId}/status/`)
            .then(r => r.json())
            .then(data => {
                const bar = document.getElementById('progress-bar');
                const pctText = document.getElementById('progress-text');
                const msgEl = document.getElementById('status-message');
                const titleEl = document.getElementById('status-title');

                bar.style.width = data.progress_percent + '%';
                pctText.textContent = data.progress_percent + '%';
                msgEl.textContent = data.progress_message;
                updateSteps(data.progress_percent);

                if (data.status === 'completed') {
                    document.getElementById('spinner-icon').classList.add('hidden');
                    document.getElementById('success-animation').classList.remove('hidden');
                    titleEl.textContent = 'Conversion complete!';
                    msgEl.textContent = 'Redirecting to editor...';
                    document.getElementById('status-icon').classList.add('hidden');
                    clearInterval(pollTimer);
                    setTimeout(() => { window.location.href = `/editor/${projectId}/?autocompile=true`; }, 2000);
                } else if (data.status === 'failed') {
                    document.getElementById('spinner-icon').classList.add('hidden');
                    document.getElementById('error-animation').classList.remove('hidden');
                    titleEl.textContent = 'Conversion failed';
                    msgEl.textContent = data.error_message || data.progress_message;
                    document.getElementById('status-icon').classList.add('hidden');
                    document.getElementById('error-actions').classList.remove('hidden');
                    bar.classList.remove('bg-primary');
                    bar.classList.add('bg-error');
                    clearInterval(pollTimer);
                }
            })
            .catch(() => {});
    }

    pollTimer = setInterval(pollStatus, pollInterval);
    pollStatus();
})();
