document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const profileStatusBadge = document.getElementById('profile-status-badge');
  const profileName = document.getElementById('profile-name');
  const profileSub = document.getElementById('profile-sub');
  const profileInitials = document.getElementById('profile-initials');
  const profileCharCount = document.getElementById('profile-char-count');
  const profileSectionCount = document.getElementById('profile-section-count');
  
  const tabUploadBtn = document.getElementById('tab-upload-btn');
  const tabUrlBtn = document.getElementById('tab-url-btn');
  const uploadTab = document.getElementById('upload-tab');
  const urlTab = document.getElementById('url-tab');
  
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const fileSelectedInfo = document.getElementById('file-selected-info');
  const selectedFileName = document.getElementById('selected-file-name');
  const cancelFileBtn = document.getElementById('cancel-file-btn');
  const submitFileBtn = document.getElementById('submit-file-btn');
  
  const urlInput = document.getElementById('url-input');
  const submitUrlBtn = document.getElementById('submit-url-btn');
  
  const viewMarkdownBtn = document.getElementById('view-markdown-btn');
  const previewModal = document.getElementById('preview-modal');
  const closeModalBtn = document.getElementById('close-modal-btn');
  const copyMarkdownBtn = document.getElementById('copy-markdown-btn');
  const markdownCodeView = document.getElementById('markdown-code-view');
  
  const chatForm = document.getElementById('chat-form');
  const chatInput = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send-btn');
  const messagesArea = document.getElementById('messages-area');
  const welcomeCard = document.getElementById('welcome-card');
  const typingIndicator = document.getElementById('typing-indicator');
  const clearChatBtn = document.getElementById('clear-chat-btn');
  
  const sidebar = document.getElementById('sidebar');
  const openSidebarBtn = document.getElementById('open-sidebar-btn');
  const toggleSidebarBtn = document.getElementById('toggle-sidebar-btn');
  const toastContainer = document.getElementById('toast-container');

  // Chat State
  let chatHistory = [];
  let currentProfileMarkdown = '';
  let selectedFile = null;

  // Initialize
  fetchCurrentProfile();

  // Mobile sidebar controls
  if (openSidebarBtn) {
    openSidebarBtn.addEventListener('click', () => sidebar.classList.add('open'));
  }
  if (toggleSidebarBtn) {
    toggleSidebarBtn.addEventListener('click', () => sidebar.classList.remove('open'));
  }

  // Tabs
  tabUploadBtn.addEventListener('click', () => {
    tabUploadBtn.classList.add('active');
    tabUrlBtn.classList.remove('active');
    uploadTab.classList.add('active');
    urlTab.classList.remove('active');
  });

  tabUrlBtn.addEventListener('click', () => {
    tabUrlBtn.classList.add('active');
    tabUploadBtn.classList.remove('active');
    urlTab.classList.add('active');
    uploadTab.classList.remove('active');
  });

  // Fetch Profile Metadata
  async function fetchCurrentProfile() {
    try {
      profileStatusBadge.textContent = 'Checking...';
      profileStatusBadge.className = 'status-pill status-loading';
      
      const res = await fetch('/api/profile');
      if (!res.ok) throw new Error('Failed to fetch profile');
      const data = await res.json();
      
      if (data.exists && data.markdown) {
        currentProfileMarkdown = data.markdown;
        updateProfileUI(data.markdown);
      } else {
        profileStatusBadge.textContent = 'No Profile';
        profileStatusBadge.className = 'status-pill status-empty';
        profileName.textContent = 'No Profile Loaded';
        profileSub.textContent = 'Upload or paste a URL';
        profileInitials.textContent = '--';
        profileCharCount.textContent = '0';
        profileSectionCount.textContent = '0';
        currentProfileMarkdown = '';
      }
    } catch (err) {
      console.error(err);
      profileStatusBadge.textContent = 'Offline';
      profileStatusBadge.className = 'status-pill status-empty';
    }
  }

  function updateProfileUI(markdown) {
    profileStatusBadge.textContent = 'Active';
    profileStatusBadge.className = 'status-pill status-ready';

    // Parse candidate name from first heading
    const nameMatch = markdown.match(/^#\s+(.+)$/m);
    const candidateName = nameMatch ? nameMatch[1].trim() : 'Alex Rivera';
    profileName.textContent = candidateName;

    // Initials
    const initials = candidateName
      .split(' ')
      .filter(w => w.length > 0)
      .map(w => w[0].toUpperCase())
      .slice(0, 2)
      .join('');
    profileInitials.textContent = initials || 'ME';

    // Title / subtitle
    const subMatch = markdown.match(/\*\*(.+?)\*\*/);
    profileSub.textContent = subMatch ? subMatch[1] : 'LinkedIn Profile';

    // Stats
    profileCharCount.textContent = markdown.length.toLocaleString();
    const sections = (markdown.match(/^##\s+/gm) || []).length;
    profileSectionCount.textContent = sections.toString();

    // Code view
    markdownCodeView.textContent = markdown;
  }

  // Drag and Drop & File Upload
  dropZone.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover'].forEach(name => {
    dropZone.addEventListener(name, (e) => {
      e.preventDefault();
      dropZone.classList.add('drag-over');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropZone.addEventListener(name, (e) => {
      e.preventDefault();
      dropZone.classList.remove('drag-over');
    });
  });

  dropZone.addEventListener('drop', (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleSelectedFile(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files.length > 0) {
      handleSelectedFile(fileInput.files[0]);
    }
  });

  function handleSelectedFile(file) {
    const allowed = ['pdf', 'docx', 'doc', 'txt', 'html', 'htm', 'md'];
    const ext = file.name.split('.').pop().toLowerCase();

    if (!allowed.includes(ext)) {
      showToast(`Invalid file type .${ext}. Please select PDF, DOCX, DOC, TXT, HTML, or MD.`, 'error');
      return;
    }

    if (file.size > 15 * 1024 * 1024) {
      showToast('File size exceeds 15MB limit.', 'error');
      return;
    }

    selectedFile = file;
    selectedFileName.textContent = file.name;
    fileSelectedInfo.classList.remove('hidden');
    submitFileBtn.disabled = false;
  }

  cancelFileBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    selectedFile = null;
    fileInput.value = '';
    fileSelectedInfo.classList.add('hidden');
    submitFileBtn.disabled = true;
  });

  submitFileBtn.addEventListener('click', async () => {
    if (!selectedFile) return;

    submitFileBtn.disabled = true;
    submitFileBtn.textContent = 'Extracting text...';

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Upload failed');
      }

      showToast('Profile parsed and updated successfully!', 'success');
      currentProfileMarkdown = data.markdown;
      updateProfileUI(data.markdown);
      
      // Reset input state
      selectedFile = null;
      fileInput.value = '';
      fileSelectedInfo.classList.add('hidden');
      submitFileBtn.disabled = true;

    } catch (err) {
      console.error(err);
      showToast(err.message, 'error');
    } finally {
      submitFileBtn.textContent = 'Extract & Replace Profile';
      submitFileBtn.disabled = !selectedFile;
    }
  });

  // URL Submission
  submitUrlBtn.addEventListener('click', async () => {
    const url = urlInput.value.trim();
    if (!url) {
      showToast('Please enter a valid URL.', 'error');
      return;
    }

    submitUrlBtn.disabled = true;
    submitUrlBtn.textContent = 'Fetching webpage...';

    const formData = new FormData();
    formData.append('url', url);

    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to fetch webpage');
      }

      showToast('Profile imported successfully from URL!', 'success');
      currentProfileMarkdown = data.markdown;
      updateProfileUI(data.markdown);
      urlInput.value = '';

    } catch (err) {
      console.error(err);
      showToast(err.message, 'error');
    } finally {
      submitUrlBtn.disabled = false;
      submitUrlBtn.textContent = 'Fetch & Convert Webpage';
    }
  });

  // Markdown Preview Modal
  viewMarkdownBtn.addEventListener('click', () => {
    if (!currentProfileMarkdown) {
      showToast('No profile markdown loaded yet.', 'info');
      return;
    }
    markdownCodeView.textContent = currentProfileMarkdown;
    previewModal.classList.remove('hidden');
  });

  closeModalBtn.addEventListener('click', () => {
    previewModal.classList.add('hidden');
  });

  previewModal.addEventListener('click', (e) => {
    if (e.target === previewModal) {
      previewModal.classList.add('hidden');
    }
  });

  copyMarkdownBtn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(currentProfileMarkdown);
      copyMarkdownBtn.textContent = 'Copied!';
      setTimeout(() => {
        copyMarkdownBtn.textContent = 'Copy';
      }, 2000);
    } catch {
      showToast('Failed to copy to clipboard', 'error');
    }
  });

  // Auto-resize textarea
  chatInput.addEventListener('input', () => {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
  });

  // Handle enter key to send
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleChatSubmit();
    }
  });

  chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    handleChatSubmit();
  });

  // Suggestion chips
  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const question = chip.getAttribute('data-question');
      if (question) {
        chatInput.value = question;
        handleChatSubmit();
      }
    });
  });

  // Clear chat
  clearChatBtn.addEventListener('click', () => {
    chatHistory = [];
    messagesArea.innerHTML = '';
    if (welcomeCard) {
      messagesArea.appendChild(welcomeCard);
      welcomeCard.classList.remove('hidden');
    }
    showToast('Conversation cleared.', 'info');
  });

  // Chat Execution
  async function handleChatSubmit() {
    const text = chatInput.value.trim();
    if (!text) return;

    // Reset textarea
    chatInput.value = '';
    chatInput.style.height = 'auto';

    // Hide welcome card once chat starts
    if (welcomeCard && !welcomeCard.classList.contains('hidden')) {
      welcomeCard.classList.add('hidden');
    }

    // Append User Message Bubble
    appendMessage('user', text);
    chatHistory.push({ role: 'user', content: text });

    // Show Typing Indicator
    showTyping(true);
    sendBtn.disabled = true;

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          history: chatHistory.slice(-8)
        })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to get response');
      }

      showTyping(false);
      appendMessage('assistant', data.reply, data.section_heading);
      chatHistory.push({ role: 'assistant', content: data.reply });

    } catch (err) {
      showTyping(false);
      console.error(err);
      appendMessage('assistant', `⚠️ ${err.message}`);
      showToast(err.message, 'error');
    } finally {
      sendBtn.disabled = false;
      chatInput.focus();
    }
  }

  function appendMessage(role, text, sectionHeading = null) {
    const row = document.createElement('div');
    row.className = `message-row ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role === 'user' ? 'You' : 'AI';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.textContent = text;
    contentDiv.appendChild(bubble);

    // If assistant has a supporting section heading, add a badge
    if (role === 'assistant' && sectionHeading) {
      const badge = document.createElement('div');
      badge.className = 'source-badge';
      badge.innerHTML = `
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
        </svg>
        Source: ${escapeHtml(sectionHeading)}
      `;
      contentDiv.appendChild(badge);
    }

    row.appendChild(avatar);
    row.appendChild(contentDiv);

    messagesArea.appendChild(row);
    messagesArea.scrollTop = messagesArea.scrollHeight;
  }

  function showTyping(show) {
    if (show) {
      typingIndicator.classList.remove('hidden');
      messagesArea.appendChild(typingIndicator);
      messagesArea.scrollTop = messagesArea.scrollHeight;
    } else {
      typingIndicator.classList.add('hidden');
    }
  }

  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let icon = 'ℹ️';
    if (type === 'success') icon = '✓';
    if (type === 'error') icon = '⚠️';

    toast.innerHTML = `<span>${icon}</span><span>${escapeHtml(message)}</span>`;
    toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4500);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, m => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    }[m]));
  }
});
