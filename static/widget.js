(function() {
    'use strict';
    
    // Configuration
    const WIDGET_ID = 'docupload-widget';
    let API_BASE_URL = '';

    function getBaseUrl() {
        // Find the script element that loaded this widget
        const scripts = document.getElementsByTagName('script');
        for (let i = 0; i < scripts.length; i++) {
            if (scripts[i].src && scripts[i].src.includes('widget.js')) {
                const url = new URL(scripts[i].src);
                return `${url.protocol}//${url.host}`;
            }
        }
        return window.location.origin; // Fallback
    }

    API_BASE_URL = getBaseUrl();

    function createWidgetUI(container) {
        // Inject styles
        const style = document.createElement('style');
        style.textContent = `
            #${WIDGET_ID} {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                color: #2d3748;
            }
            
            .du-section { 
                margin-bottom: 1.75rem; 
            }
            
            .du-label { 
                display: block; 
                font-weight: 600; 
                margin-bottom: 0.5rem; 
                font-size: 0.95rem;
                color: #2d3748;
            }
            
            .du-required {
                color: #e53e3e;
            }
            
            .du-input-text {
                width: 100%;
                padding: 0.75rem;
                border: 2px solid #e2e8f0;
                border-radius: 0.5rem;
                font-size: 0.95rem;
                transition: border-color 0.2s;
                font-family: inherit;
            }
            
            .du-input-text:focus {
                outline: none;
                border-color: #4299e1;
            }
            
            .du-drop-zone {
                border: 2px dashed #cbd5e0;
                border-radius: 0.5rem;
                padding: 2rem 1rem;
                text-align: center;
                cursor: pointer;
                transition: all 0.2s;
                background-color: #f7fafc;
            }
            
            .du-drop-zone:hover {
                border-color: #4299e1;
                background-color: #ebf8ff;
            }
            
            .du-drop-zone.dragover {
                border-color: #4299e1;
                background-color: #bee3f8;
                transform: scale(1.02);
            }
            
            .du-drop-zone.has-file {
                border-style: solid;
                border-color: #48bb78;
                background-color: #f0fff4;
            }
            
            .du-drop-icon {
                font-size: 2.5rem;
                margin-bottom: 0.5rem;
            }
            
            .du-drop-text {
                font-size: 0.95rem;
                color: #4a5568;
                margin: 0;
            }
            
            .du-file-info {
                display: none;
                align-items: center;
                justify-content: center;
                gap: 0.5rem;
            }
            
            .du-file-info.show {
                display: flex;
            }
            
            .du-file-name { 
                font-weight: 600; 
                font-size: 0.95rem;
                color: #2d3748;
            }
            
            .du-file-size {
                font-size: 0.85rem;
                color: #718096;
            }
            
            .du-helper { 
                color: #718096; 
                font-size: 0.85rem; 
                margin-top: 0.5rem;
                font-style: italic;
            }
            
            .du-btn {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 1rem 2rem;
                border-radius: 0.5rem;
                border: none;
                cursor: pointer;
                font-weight: 600;
                width: 100%;
                font-size: 1rem;
                transition: transform 0.2s, box-shadow 0.2s;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            
            .du-btn:hover:not(:disabled) { 
                transform: translateY(-2px);
                box-shadow: 0 6px 12px rgba(0,0,0,0.15);
            }
            
            .du-btn:active:not(:disabled) {
                transform: translateY(0);
            }
            
            .du-btn:disabled { 
                background: #a0aec0; 
                cursor: not-allowed;
                transform: none;
            }
            
            .du-alert {
                padding: 1rem;
                border-radius: 0.5rem;
                margin-top: 1.5rem;
                display: none;
                font-size: 0.9rem;
                line-height: 1.5;
            }
            
            .du-alert.show {
                display: block;
            }
            
            .du-error { 
                background-color: #fed7d7;
                color: #742a2a;
                border-left: 4px solid #e53e3e;
            }
            
            .du-success { 
                background-color: #c6f6d5;
                color: #22543d;
                border-left: 4px solid #38a169;
            }
            
            .du-hidden { 
                display: none !important; 
            }
            
            .du-tag-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 1rem;
            }
            
            @media (max-width: 640px) {
                .du-tag-grid {
                    grid-template-columns: 1fr;
                }
            }
        `;
        document.head.appendChild(style);

        // HTML Structure
        container.innerHTML = `
            <div>
                <!-- Tags Section -->
                <div class="du-section">
                    <h3 style="margin: 0 0 1.5rem 0; font-size: 1.1rem; color: #2d3748;">Project Metadata</h3>
                    
                    <div class="du-tag-grid">
                        <div>
                            <label class="du-label">
                                Project Name <span class="du-required">*</span>
                            </label>
                            <input 
                                type="text" 
                                id="du-tag-project" 
                                class="du-input-text" 
                                placeholder="e.g., sis"
                                required
                            >
                            <p class="du-helper">Lowercase, numbers, hyphens (1-32 chars)</p>
                        </div>
                        
                        <div>
                            <label class="du-label">Environment</label>
                            <select id="du-tag-env" class="du-input-text">
                                <option value="">Select environment</option>
                                <option value="dev">Development</option>
                                <option value="test">Test</option>
                                <option value="staging">Staging</option>
                                <option value="prod">Production</option>
                            </select>
                        </div>
                    </div>
                    
                    <div style="margin-top: 1rem;">
                        <label class="du-label">Domain (Optional)</label>
                        <input 
                            type="text" 
                            id="du-tag-domain" 
                            class="du-input-text" 
                            placeholder="e.g., student"
                        >
                        <p class="du-helper">Alphanumeric, spaces, hyphens, underscores (1-64 chars)</p>
                    </div>
                </div>

                <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 2rem 0;">

                <!-- Architecture Diagram -->
                <div class="du-section">
                    <label class="du-label">
                        Architectural Diagram <span class="du-required">*</span>
                    </label>
                    <div class="du-drop-zone" id="du-zone-arch">
                        <div class="du-drop-content">
                            <div class="du-drop-icon">📄</div>
                            <p class="du-drop-text">
                                <strong>Click to select</strong> or drag PDF here
                            </p>
                        </div>
                        <div class="du-file-info">
                            <span>✅</span>
                            <div>
                                <div class="du-file-name"></div>
                                <div class="du-file-size"></div>
                            </div>
                        </div>
                    </div>
                    <input type="file" id="du-input-arch" accept=".pdf" class="du-hidden">
                    <p class="du-helper">Upload a PDF architecture diagram (max 25 MB)</p>
                </div>

                <!-- Charter -->
                <div class="du-section">
                    <label class="du-label">
                        Charter Document <span class="du-required">*</span>
                    </label>
                    <div class="du-drop-zone" id="du-zone-charter">
                        <div class="du-drop-content">
                            <div class="du-drop-icon">📝</div>
                            <p class="du-drop-text">
                                <strong>Click to select</strong> or drag DOCX here
                            </p>
                        </div>
                        <div class="du-file-info">
                            <span>✅</span>
                            <div>
                                <div class="du-file-name"></div>
                                <div class="du-file-size"></div>
                            </div>
                        </div>
                    </div>
                    <input type="file" id="du-input-charter" accept=".docx" class="du-hidden">
                    <p class="du-helper">Upload a DOCX charter document (max 25 MB)</p>
                </div>

                <button id="du-submit-btn" class="du-btn">
                    Submit Artifacts
                </button>

                <div id="du-error-msg" class="du-alert du-error"></div>
                <div id="du-success-msg" class="du-alert du-success"></div>
            </div>
        `;

        // DOM Elements
        const els = {
            project: container.querySelector('#du-tag-project'),
            env: container.querySelector('#du-tag-env'),
            domain: container.querySelector('#du-tag-domain'),
            submitBtn: container.querySelector('#du-submit-btn'),
            errorMsg: container.querySelector('#du-error-msg'),
            successMsg: container.querySelector('#du-success-msg'),
            arch: {
                zone: container.querySelector('#du-zone-arch'),
                input: container.querySelector('#du-input-arch'),
                content: container.querySelector('#du-zone-arch .du-drop-content'),
                fileInfo: container.querySelector('#du-zone-arch .du-file-info'),
                fileName: container.querySelector('#du-zone-arch .du-file-name'),
                fileSize: container.querySelector('#du-zone-arch .du-file-size'),
                file: null
            },
            charter: {
                zone: container.querySelector('#du-zone-charter'),
                input: container.querySelector('#du-input-charter'),
                content: container.querySelector('#du-zone-charter .du-drop-content'),
                fileInfo: container.querySelector('#du-zone-charter .du-file-info'),
                fileName: container.querySelector('#du-zone-charter .du-file-name'),
                fileSize: container.querySelector('#du-zone-charter .du-file-size'),
                file: null
            }
        };

        // Utility Functions
        function formatFileSize(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
        }

        function showError(msg) {
            els.errorMsg.textContent = msg;
            els.errorMsg.classList.add('show');
            els.successMsg.classList.remove('show');
            // Scroll to error
            els.errorMsg.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        function showSuccess(msg) {
            els.successMsg.innerHTML = msg;
            els.successMsg.classList.add('show');
            els.errorMsg.classList.remove('show');
            // Scroll to success
            els.successMsg.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        function clearMessages() {
            els.errorMsg.classList.remove('show');
            els.successMsg.classList.remove('show');
        }

        // File Handler Setup
        function setupFileHandler(key, acceptExt, maxSize) {
            const fileData = els[key];
            const { zone, input, content, fileInfo, fileName, fileSize } = fileData;

            // Click to open file dialog
            zone.addEventListener('click', () => input.click());

            // Drag and drop events
            zone.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.stopPropagation();
                zone.classList.add('dragover');
            });

            zone.addEventListener('dragleave', (e) => {
                e.preventDefault();
                e.stopPropagation();
                zone.classList.remove('dragover');
            });

            zone.addEventListener('drop', (e) => {
                e.preventDefault();
                e.stopPropagation();
                zone.classList.remove('dragover');
                
                if (e.dataTransfer.files.length > 0) {
                    handleFile(e.dataTransfer.files[0]);
                }
            });

            // File input change
            input.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    handleFile(e.target.files[0]);
                }
            });

            function handleFile(file) {
                clearMessages();

                // Validate extension
                if (!file.name.toLowerCase().endsWith(acceptExt)) {
                    showError(`Invalid file type. Only ${acceptExt.toUpperCase()} files are allowed for this field.`);
                    return;
                }

                // Validate size
                if (file.size > maxSize) {
                    showError(`File too large. Maximum size is ${formatFileSize(maxSize)}.`);
                    return;
                }

                if (file.size === 0) {
                    showError('File is empty. Please select a valid file.');
                    return;
                }

                // Store file
                fileData.file = file;
                
                // Update UI
                zone.classList.add('has-file');
                content.style.display = 'none';
                fileInfo.classList.add('show');
                fileName.textContent = file.name;
                fileSize.textContent = formatFileSize(file.size);
            }
        }

        const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25MB
        setupFileHandler('arch', '.pdf', MAX_FILE_SIZE);
        setupFileHandler('charter', '.docx', MAX_FILE_SIZE);

        // Form Submission
        els.submitBtn.addEventListener('click', async () => {
            clearMessages();

            // Validate files
            if (!els.arch.file) {
                showError('Architectural Diagram (PDF) is required.');
                return;
            }

            if (!els.charter.file) {
                showError('Charter Document (DOCX) is required.');
                return;
            }

            // Validate project name
            const projectValue = els.project.value.trim();
            if (!projectValue) {
                showError('Project Name is required.');
                return;
            }

            const projectRegex = /^[a-z0-9-]{1,32}$/;
            if (!projectRegex.test(projectValue)) {
                showError('Project Name format is invalid. Use lowercase letters, numbers, and hyphens only (1-32 characters).');
                return;
            }

            // Build tags
            const tags = {
                project: projectValue
            };

            if (els.env.value) {
                tags.environment = els.env.value;
            }

            const domainValue = els.domain.value.trim();
            if (domainValue) {
                const domainRegex = /^[A-Za-z0-9 _.-]{1,64}$/;
                if (!domainRegex.test(domainValue)) {
                    showError('Domain format is invalid. Use alphanumeric characters, spaces, hyphens, underscores, and periods only (1-64 characters).');
                    return;
                }
                tags.domain = domainValue;
            }

            // Build FormData
            const formData = new FormData();
            formData.append('architectureDiagram', els.arch.file);
            formData.append('charter', els.charter.file);
            formData.append('tags', JSON.stringify(tags));

            // Disable button and show loading
            els.submitBtn.disabled = true;
            els.submitBtn.textContent = '⏳ Uploading & Processing...';

            try {
                const response = await fetch(`${API_BASE_URL}/upload`, {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || `Upload failed with status ${response.status}`);
                }

                // Success
                showSuccess(`
                    <strong>✅ Upload Successful!</strong><br><br>
                    <strong>Submission ID:</strong> ${data.submissionId}<br>
                    <strong>Status:</strong> ${data.scanStatus}<br>
                    <strong>Blob Path:</strong> ${data.blobPath}<br>
                    <strong>ZIP Hash:</strong> <code style="word-break: break-all;">${data.zipSha256}</code>
                `);

                // Reset form
                resetForm();

            } catch (err) {
                showError(`❌ Upload failed: ${err.message}`);
            } finally {
                els.submitBtn.disabled = false;
                els.submitBtn.textContent = 'Submit Artifacts';
            }
        });

        function resetForm() {
            // Reset inputs
            els.project.value = '';
            els.env.value = '';
            els.domain.value = '';

            // Reset file handlers
            ['arch', 'charter'].forEach(key => {
                const fileData = els[key];
                fileData.file = null;
                fileData.input.value = '';
                fileData.zone.classList.remove('has-file');
                fileData.content.style.display = '';
                fileData.fileInfo.classList.remove('show');
            });
        }
    }

    // Initialize widget when DOM is ready
    function initWidget() {
        const container = document.getElementById(WIDGET_ID);
        if (container) {
            createWidgetUI(container);
        } else {
            console.error(`Widget container with ID "${WIDGET_ID}" not found.`);
        }
    }

    // Initialize
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initWidget);
    } else {
        initWidget();
    }

})();
