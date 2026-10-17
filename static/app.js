let currentProject = localStorage.getItem('capcut_last_project') || "";
let projectData = null;
let selectedSegment = null;
let currentPlayheadUs = 0;
let isPlaying = false;
let playAnimFrameId = null;
let playStartTime = 0;
let playStartUs = 0;
let zoomFactor = 1.0;
let currentTool = "select"; // 'select' or 'razor'
let isDraggingClip = false;
let dragStartX = 0;
let dragOrigStartUs = 0;

// AI Agent & Bounding Box State
let detectedErrors = [];
let currentErrorFilter = 'all';
let showBBoxOverlay = false;
let isAgentAutoRunning = false;
let agentAutoTimer = null;
let agentFixedIds = new Set();
let scanDebounceTimer = null;

const PX_PER_SECOND_BASE = 85;

// Helper: Escape chuỗi chống XSS
function esc(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// Helper: Ẩn thông tin thư mục người dùng cá nhân
function maskUserPath(p) {
  if (!p) return '--';
  let str = String(p).replace(/\\/g, '/');
  str = str.replace(/^[a-zA-Z]:\/Users\/[^/]+/i, '~');
  const parts = str.split('/');
  if (parts.length > 3) {
    return '.../' + parts.slice(-3).join('/');
  }
  return str;
}

// Helper: Hệ thống Toast notification góc dưới phải
function getToastContainer() {
  let c = document.getElementById('toastContainer');
  if (!c) {
    c = document.createElement('div');
    c.id = 'toastContainer';
    c.className = 'toast-container';
    document.body.appendChild(c);
  }
  return c;
}

function showToast(message, type = 'info', actionText = null, actionCb = null, duration = 4000) {
  const container = getToastContainer();
  const toast = document.createElement('div');
  toast.className = `toast-item toast-${type}`;
  
  const icon = type === 'success' ? '✓' : (type === 'error' ? '✕' : (type === 'warn' ? '⚠' : 'ℹ'));
  
  let html = `<span class="toast-icon">${icon}</span><span class="toast-msg">${esc(message)}</span>`;
  if (actionText && typeof actionCb === 'function') {
    html += `<button class="toast-action-btn" type="button">${esc(actionText)}</button>`;
  }
  html += `<button class="toast-close-btn" type="button">&times;</button>`;
  toast.innerHTML = html;
  
  if (actionText && typeof actionCb === 'function') {
    const actBtn = toast.querySelector('.toast-action-btn');
    actBtn.onclick = () => {
      try { actionCb(); } catch (e) { console.error(e); }
      toast.remove();
    };
  }
  
  toast.querySelector('.toast-close-btn').onclick = () => toast.remove();
  
  container.appendChild(toast);
  
  setTimeout(() => {
    toast.classList.add('toast-fade-out');
    setTimeout(() => toast.remove(), 250);
  }, duration);
}

// Debounce quét lỗi timeline
function debouncedScanErrors(delay = 600) {
  clearTimeout(scanDebounceTimer);
  scanDebounceTimer = setTimeout(() => {
    scanCurrentProjectErrors();
  }, delay);
}

window.addEventListener('DOMContentLoaded', async () => {
  initSplitters();
  checkCapCutStatus();
  await fetchProjects();
  if (currentProject) {
    await loadProject(currentProject);
  }
  setupTimelineInteractions();
  setupKeyboardShortcuts();
});

// Kiểm tra trạng thái CapCut Desktop đang chạy (Mục 2.3 & Phase 5)
async function checkCapCutStatus() {
  try {
    const res = await fetch('/api/capcut-status');
    const data = await res.json();
    const isRunning = Boolean(data.capcut_running || data.running || data.is_running);
    const banner = document.getElementById('capcutStatusBanner');
    if (banner) {
      banner.style.display = isRunning ? 'flex' : 'none';
    }
    if (isRunning) {
      showToast('CapCut đang mở — chỉnh sửa bị khóa', 'warn');
    }
  } catch (e) {
    console.debug('Failed to check capcut status:', e);
  }
}

// Khởi tạo các Splitter kéo đổi kích thước 3 cột và timeline (Lưu localStorage)
function initSplitters() {
  // 1. Splitter trái: Thư viện
  const splLeft = document.getElementById('splitterLeft');
  const panelAssets = document.getElementById('panelAssets');
  if (splLeft && panelAssets) {
    const savedW = localStorage.getItem('capcut_asset_width');
    if (savedW) panelAssets.style.width = `${savedW}px`;
    
    let isDragging = false;
    splLeft.addEventListener('mousedown', (e) => {
      isDragging = true;
      splLeft.classList.add('active');
      document.body.style.cursor = 'col-resize';
      e.preventDefault();
    });
    window.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      const newW = Math.max(240, Math.min(480, e.clientX));
      panelAssets.style.width = `${newW}px`;
      localStorage.setItem('capcut_asset_width', newW);
    });
    window.addEventListener('mouseup', () => {
      if (isDragging) {
        isDragging = false;
        splLeft.classList.remove('active');
        document.body.style.cursor = '';
      }
    });
  }

  // 2. Splitter phải: Inspector
  const splRight = document.getElementById('splitterRight');
  const panelDetails = document.getElementById('panelDetails');
  if (splRight && panelDetails) {
    const savedW = localStorage.getItem('capcut_inspector_width');
    if (savedW) panelDetails.style.width = `${savedW}px`;
    if (localStorage.getItem('capcut_inspector_folded') === 'true') {
      panelDetails.classList.add('folded');
    }
    
    let isDragging = false;
    splRight.addEventListener('mousedown', (e) => {
      isDragging = true;
      splRight.classList.add('active');
      document.body.style.cursor = 'col-resize';
      e.preventDefault();
    });
    window.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      const newW = Math.max(240, Math.min(480, window.innerWidth - e.clientX));
      panelDetails.style.width = `${newW}px`;
      localStorage.setItem('capcut_inspector_width', newW);
    });
    window.addEventListener('mouseup', () => {
      if (isDragging) {
        isDragging = false;
        splRight.classList.remove('active');
        document.body.style.cursor = '';
      }
    });
  }

  // 3. Splitter ngang: Chiều cao Timeline
  const splTl = document.getElementById('splitterTimeline');
  const lowerTimeline = document.getElementById('lowerTimeline');
  if (splTl && lowerTimeline) {
    const savedH = localStorage.getItem('capcut_timeline_height');
    if (savedH) lowerTimeline.style.height = `${savedH}px`;
    
    let isDragging = false;
    splTl.addEventListener('mousedown', (e) => {
      isDragging = true;
      splTl.classList.add('active');
      document.body.style.cursor = 'row-resize';
      e.preventDefault();
    });
    window.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      const newH = Math.max(160, Math.min(window.innerHeight * 0.7, window.innerHeight - e.clientY));
      lowerTimeline.style.height = `${newH}px`;
      localStorage.setItem('capcut_timeline_height', newH);
    });
    window.addEventListener('mouseup', () => {
      if (isDragging) {
        isDragging = false;
        splTl.classList.remove('active');
        document.body.style.cursor = '';
      }
    });
  }
}

// Bật/tắt gập Inspector phải
function toggleInspectorFold() {
  const panel = document.getElementById('panelDetails');
  if (!panel) return;
  const isFolded = panel.classList.toggle('folded');
  localStorage.setItem('capcut_inspector_folded', isFolded);
}

// Sao chép văn bản vào bộ nhớ tạm
function copyTextToClipboard(text) {
  if (!text || text === '--') return;
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(() => {
      showToast('Đã sao chép đường dẫn', 'success');
    }).catch(() => {
      showToast('Không thể sao chép', 'warn');
    });
  }
}

// Nút Lưu dự án
function saveDraftAction() {
  showToast(`Dự án "${currentProject || 'Hiện tại'}" đã được đồng bộ trực tiếp vào draft CapCut. Bạn có thể mở CapCut để xem kết quả.`, 'success', null, null, 4000);
}
const exportDraft = saveDraftAction;

// 1. Fetch available projects
async function fetchProjects() {
  try {
    const res = await fetch('/api/projects');
    if (!res.ok) {
      showToast('Không thể tải danh sách dự án CapCut', 'error');
      return;
    }
    const data = await res.json();
    const select = document.getElementById('projectSelect');
    if (!select) return;
    select.innerHTML = '';
    
    if (data.warning) {
      showToast(data.warning, 'warn', null, null, 6000);
    }
    
    const projects = data.projects || [];
    if (projects.length === 0) {
      const opt = document.createElement('option');
      opt.textContent = '(Không tìm thấy dự án CapCut)';
      select.appendChild(opt);
      renderProjectErrorState('', 'Không tìm thấy dự án CapCut nào trên máy tính.');
      return;
    }
    
    // Ưu tiên: 1. Project đã lưu trong localStorage; 2. Project có footage; 3. Project đầu tiên
    const saved = localStorage.getItem('capcut_last_project');
    const hasSaved = projects.find(p => p.name === saved);
    if (hasSaved) {
      currentProject = saved;
    } else {
      const preferred = projects.find(p => p.has_footage && !p.error) || projects[0];
      currentProject = preferred ? preferred.name : projects[0].name;
    }
    
    projects.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.name;
      let tag = p.has_footage ? `🎬 (${p.video_count} clip · ${p.duration_sec}s)` : `(Text & FX)`;
      if (p.error) tag = `⚠️ [Lỗi draft]`;
      opt.textContent = `${p.name} ${tag}`;
      if (p.name === currentProject) opt.selected = true;
      select.appendChild(opt);
    });
  } catch (err) {
    console.error('Failed to fetch projects:', err);
    showToast('Lỗi kết nối máy chủ CapCut Web Studio', 'error');
  }
}

// 2. Load project data
let currentComponentFilter = 'all';

function renderProjectErrorState(projectName, errorMsg) {
  const container = document.getElementById('tracksContainer');
  if (container) {
    container.innerHTML = `
      <div class="project-error-card">
        <div class="project-error-icon">⚠️</div>
        <div class="project-error-title">Không thể tải dự án "${esc(projectName || 'Chưa chọn')}"</div>
        <div class="project-error-desc">${esc(errorMsg || 'Vui lòng kiểm tra lại file draft_content.json')}</div>
        <div class="project-error-hints">
          <div>• Đảm bảo phần mềm CapCut Desktop đã được đóng hoàn toàn.</div>
          <div>• Kiểm tra xem draft có bị mã hóa hoặc file JSON bị hỏng không.</div>
          <div>• Kiểm tra biến môi trường CAPCUT_DRAFTS_DIR trỏ đúng thư mục dự án.</div>
        </div>
        <button class="btn-retry-load" type="button" onclick="fetchProjects()">🔄 Tải lại danh sách dự án</button>
      </div>
    `;
  }
}

async function loadProject(projectName, preserveView = false) {
  if (!projectName) return;
  currentProject = projectName;
  
  // Lưu vị trí scroll và zoom hiện tại nếu preserveView
  const timelineScroll = document.getElementById('timelineScroll');
  const prevScrollLeft = timelineScroll ? timelineScroll.scrollLeft : 0;
  
  try {
    const res = await fetch(`/api/project/${encodeURIComponent(projectName)}`);
    if (!res.ok) {
      let detailMsg = 'Draft không đọc được hoặc không tồn tại';
      try {
        const errJson = await res.json();
        detailMsg = errJson.detail || detailMsg;
      } catch (e) {}
      renderProjectErrorState(projectName, detailMsg);
      showToast(`Không thể đọc dự án "${projectName}": ${detailMsg}`, 'error');
      return;
    }
    
    projectData = await res.json();
    localStorage.setItem('capcut_last_project', projectName);
    
    // Update Details panel
    const durSec = (projectData.duration_us || 0) / 1000000;
    const durFormatted = formatTimecode(projectData.duration_us || 0);
    
    const crumbProj = document.getElementById('crumbProjectName');
    if (crumbProj) crumbProj.textContent = projectData.project_name || 'Dự án CapCut';
    const tlSeq = document.getElementById('timelineSequenceName');
    if (tlSeq) tlSeq.textContent = projectData.project_name || 'Sequence 01';

    const detName = document.getElementById('detName'); if (detName) detName.textContent = projectData.project_name || '';
    const detPath = document.getElementById('detPath');
    if (detPath) {
      detPath.textContent = maskUserPath(projectData.path);
      detPath.title = 'Bấm để sao chép đường dẫn dự án';
    }
    const detDuration = document.getElementById('detDuration'); if (detDuration) detDuration.textContent = `${durFormatted} (${durSec.toFixed(2)}s)`;
    const detFps = document.getElementById('detFps'); if (detFps) detFps.textContent = `${projectData.fps || 30} fps · ${projectData.color_space || 'Rec. 709'}`;
    const detTracks = document.getElementById('detTracks'); if (detTracks) detTracks.textContent = `${(projectData.tracks || []).length} tracks`;
    
    // Update raw stats pills
    const stats = projectData.raw_stats || {};
    const comps = projectData.components || [];
    const statAll = document.getElementById('statAllCount'); if (statAll) statAll.textContent = comps.length;
    const statVid = document.getElementById('statVideoCount'); if (statVid) statVid.textContent = stats.video_count || 0;
    const statAud = document.getElementById('statAudioCount'); if (statAud) statAud.textContent = stats.audio_count || 0;
    const statTxt = document.getElementById('statTextCount'); if (statTxt) statTxt.textContent = stats.text_count || 0;
    const statEff = document.getElementById('statEffectCount'); if (statEff) statEff.textContent = stats.effect_count || 0;
    const statStk = document.getElementById('statStickerCount'); if (statStk) statStk.textContent = stats.sticker_count || 0;
    
    // Setup filter pills and render component list
    setupComponentFilters();
    renderComponentList(currentComponentFilter, '');
    
    // Update duration & timecode
    const totTc = document.getElementById('totalTimecode'); if (totTc) totTc.textContent = durFormatted;
    const tlTot = document.getElementById('timelineTotTC'); if (tlTot) tlTot.textContent = durFormatted;
    
    renderRuler(durSec);
    renderTracks();
    renderMediaTab();
    updatePlayheadPosition(currentPlayheadUs);
    
    if (preserveView && timelineScroll) {
      timelineScroll.scrollLeft = prevScrollLeft;
    }
    
    debouncedScanErrors(300);
  } catch (err) {
    console.error('Failed to load project:', err);
    renderProjectErrorState(projectName, err.message);
    showToast(`Lỗi khi mở dự án: ${err.message}`, 'error');
  }
}

// 2b. Component Explorer Functions
function setupComponentFilters() {
  const pills = document.querySelectorAll('.comp-stat-pill');
  pills.forEach(pill => {
    pill.onclick = () => {
      pills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      currentComponentFilter = pill.getAttribute('data-type');
      const searchVal = document.getElementById('compSearchInput')?.value || '';
      renderComponentList(currentComponentFilter, searchVal);
    };
  });
}

function filterComponentList() {
  const query = document.getElementById('compSearchInput')?.value || '';
  renderComponentList(currentComponentFilter, query);
}

function renderComponentList(typeFilter = 'all', query = '') {
  const container = document.getElementById('projectComponentList');
  if (!container) return;
  container.innerHTML = '';
  
  if (!projectData || !projectData.components || projectData.components.length === 0) {
    container.innerHTML = '<div style="color: var(--text-muted);font-size:11px;padding:12px;text-align:center;">Không có thành phần nào trong dự án.</div>';
    return;
  }
  
  const qLower = query.trim().toLowerCase();
  
  const filtered = projectData.components.filter(c => {
    // Type match
    if (typeFilter !== 'all' && c.type !== typeFilter) return false;
    // Query match
    if (qLower) {
      const matchLabel = (c.label || '').toLowerCase().includes(qLower);
      const matchPath = (c.media_path || '').toLowerCase().includes(qLower);
      const matchText = (c.details?.text || '').toLowerCase().includes(qLower);
      return matchLabel || matchPath || matchText;
    }
    return true;
  });
  
  if (filtered.length === 0) {
    container.innerHTML = `<div style="color: var(--text-muted);font-size:11px;padding:12px;text-align:center;">Không tìm thấy thành phần nào phù hợp.</div>`;
    return;
  }
  
  filtered.forEach(c => {
    const item = document.createElement('div');
    item.className = 'component-item';
    item.setAttribute('data-id', c.id);
    if (selectedSegment && selectedSegment.id === c.id) {
      item.classList.add('active-item');
    }
    
    const startSec = (c.start_us / 1e6).toFixed(2);
    const durSec = (c.duration_us / 1e6).toFixed(2);
    const endSec = (c.end_us / 1e6).toFixed(2);
    
    // Type icon
    const typeIcons = {
      video: '🎬',
      audio: '🎵',
      text: '🔤',
      effect: '✨',
      sticker: '🏷️'
    };
    const icon = typeIcons[c.type] || '📦';
    
    item.innerHTML = `
      <div class="comp-item-header">
        <span class="comp-item-type type-badge-${c.type}">${icon} ${c.type}</span>
        <span class="comp-item-title" title="${esc(c.label)}">${esc(c.label)}</span>
      </div>
      <div class="comp-item-meta">
        <span class="comp-item-time">⏱ ${startSec}s ➔ ${endSec}s (${durSec}s)</span>
        <span class="comp-item-track">Track ${c.track_index}</span>
      </div>
    `;
    
    item.onclick = () => {
      // Highlight in component list
      document.querySelectorAll('.component-item').forEach(el => el.classList.remove('active-item'));
      item.classList.add('active-item');
      
      // Highlight on timeline & select
      const clipEl = document.querySelector(`.timeline-clip[data-seg-id="${c.id}"]`);
      selectClip(c, c.track_index, clipEl);
    };
    
    container.appendChild(item);
  });
}

// 3. Render Ruler with Professional Timecode & Sub-ticks
function renderRuler(totalSec) {
  const rulerTrack = document.getElementById('rulerTrack');
  if (!rulerTrack) return;
  rulerTrack.innerHTML = '';
  
  const pxPerSec = PX_PER_SECOND_BASE * zoomFactor;
  const maxSec = Math.max(15, Math.ceil(totalSec) + 5);
  
  // Adaptive step based on zoom factor
  let step = 3;
  let subStep = 1;
  if (zoomFactor >= 2.0) { step = 1; subStep = 0.2; }
  else if (zoomFactor >= 1.2) { step = 2; subStep = 0.5; }
  else if (zoomFactor < 0.6) { step = 5; subStep = 1; }
  
  for (let s = 0; s <= maxSec; s += step) {
    const mark = document.createElement('div');
    mark.className = 'ruler-mark';
    mark.style.left = `${s * pxPerSec}px`;
    
    const mins = Math.floor(s / 60).toString().padStart(2, '0');
    const secs = (s % 60).toString().padStart(2, '0');
    mark.textContent = `${mins}:${secs}`;
    rulerTrack.appendChild(mark);
    
    // Add sub-second tick lines
    for (let sub = s + subStep; sub < s + step && sub <= maxSec; sub += subStep) {
      const subMark = document.createElement('div');
      subMark.className = 'ruler-mark-sub';
      subMark.style.left = `${sub * pxPerSec}px`;
      rulerTrack.appendChild(subMark);
    }
  }
}

// 3b. Track Control Toggles (Hide, Mute, Lock)
function toggleHideTrack(tIdx, el) {
  const track = projectData?.tracks?.[tIdx];
  if (!track) return;
  track.hidden = !track.hidden;
  const lane = document.querySelector(`.track-lane[data-track-index="${tIdx}"]`);
  if (lane) lane.classList.toggle('track-hidden', track.hidden);
  if (el) {
    el.textContent = track.hidden ? '🚫' : '👁';
    el.classList.toggle('active', track.hidden);
    el.title = track.hidden ? 'Hiện track' : 'Ẩn track';
  }
}

function toggleMuteTrack(tIdx, el) {
  const track = projectData?.tracks?.[tIdx];
  if (!track) return;
  track.muted = !track.muted;
  if (el) {
    el.textContent = track.muted ? '🔇' : '🔊';
    el.classList.toggle('muted-active', track.muted);
    el.title = track.muted ? 'Bật tiếng track' : 'Tắt tiếng track';
  }
}

function toggleLockTrack(tIdx, el) {
  const track = projectData?.tracks?.[tIdx];
  if (!track) return;
  track.locked = !track.locked;
  const lane = document.querySelector(`.track-lane[data-track-index="${tIdx}"]`);
  if (lane) lane.classList.toggle('track-locked', track.locked);
  if (el) {
    el.textContent = track.locked ? '🔒' : '🔓';
    el.classList.toggle('locked-active', track.locked);
    el.title = track.locked ? 'Mở khóa track' : 'Khóa track';
  }
}

// 4. Render Tracks and Clips (CapCut Commercial Design)
function renderTracks() {
  const container = document.getElementById('tracksContainer');
  if (!container) return;
  container.innerHTML = '';
  
  if (!projectData || !projectData.tracks) return;
  const pxPerSec = PX_PER_SECOND_BASE * zoomFactor;
  
  projectData.tracks.forEach((track, tIdx) => {
    const lane = document.createElement('div');
    lane.className = `track-lane track-type-${track.type}`;
    lane.dataset.trackIndex = tIdx;
    if (track.hidden) lane.classList.add('track-hidden');
    if (track.locked) lane.classList.add('track-locked');
    
    // TRACK HEADER (110px CapCut style with Label + Tag + 3 Icons)
    const header = document.createElement('div');
    header.className = 'track-header';
    
    // Left label and tag
    const labelCol = document.createElement('div');
    labelCol.className = 'track-label-col';
    
    // Extract short name: V1, V2, A1, T1...
    const fullLabel = track.label || `Track ${tIdx + 1}`;
    const shortCode = fullLabel.split(' ')[0] || `T${tIdx + 1}`;
    
    let tagClass = 'tag-main';
    let tagText = 'CHÍNH';
    if (track.type === 'video') {
      if (!track.is_main) { tagClass = 'tag-overlay'; tagText = 'PHỦ'; }
    } else if (track.type === 'audio') {
      if (fullLabel.includes('BGM')) { tagClass = 'tag-bgm'; tagText = 'BGM'; }
      else { tagClass = 'tag-voice'; tagText = 'THOẠI'; }
    } else if (track.type === 'text') {
      if (track.flag === 1) { tagClass = 'tag-sub'; tagText = 'SUB'; }
      else { tagClass = 'tag-text'; tagText = 'CHỮ'; }
    } else if (track.type === 'adjust' || track.type === 'effect') {
      tagClass = 'tag-fx'; tagText = 'FX';
    }
    
    labelCol.innerHTML = `
      <span class="track-main-name">${shortCode}</span>
      <span class="track-tag-pill ${tagClass}">${tagText}</span>
    `;
    
    // Right controls (Hide, Mute, Lock)
    const ctrlCol = document.createElement('div');
    ctrlCol.className = 'track-controls-col';
    ctrlCol.innerHTML = `
      <span class="track-ctrl-icon ${track.hidden ? 'active' : ''}" title="${track.hidden ? 'Hiện track' : 'Ẩn track'}" onclick="toggleHideTrack(${tIdx}, this)">${track.hidden ? '🚫' : '👁'}</span>
      <span class="track-ctrl-icon ${track.muted ? 'muted-active' : ''}" title="${track.muted ? 'Bật tiếng' : 'Tắt tiếng'}" onclick="toggleMuteTrack(${tIdx}, this)">${track.muted ? '🔇' : '🔊'}</span>
      <span class="track-ctrl-icon ${track.locked ? 'locked-active' : ''}" title="${track.locked ? 'Mở khóa' : 'Khóa track'}" onclick="toggleLockTrack(${tIdx}, this)">${track.locked ? '🔒' : '🔓'}</span>
    `;
    
    header.appendChild(labelCol);
    header.appendChild(ctrlCol);
    lane.appendChild(header);
    
    // TRACK BODY
    const body = document.createElement('div');
    body.className = 'track-body';
    
    track.segments.forEach(seg => {
      const clip = document.createElement('div');
      clip.className = 'timeline-clip';
      clip.dataset.segId = seg.id;
      clip.dataset.trackIdx = tIdx;
      
      const leftPx = (seg.start_us / 1000000) * pxPerSec;
      const widthPx = Math.max(30, (seg.duration_us / 1000000) * pxPerSec);
      
      clip.style.left = `${leftPx}px`;
      clip.style.width = `${widthPx}px`;
      clip.style.backgroundColor = seg.color || '#2d6cdf';
      
      if (selectedSegment && selectedSegment.id === seg.id) {
        clip.classList.add('selected');
      }
      
      // Video filmstrip background
      if (track.type === 'video') {
        const filmstrip = document.createElement('div');
        filmstrip.className = 'clip-filmstrip-bg';
        clip.appendChild(filmstrip);
      }
      
      // Audio waveform SVG
      if (track.type === 'audio') {
        const wf = document.createElement('div');
        wf.className = 'clip-waveform-svg';
        wf.innerHTML = `<svg width="100%" height="100%" preserveAspectRatio="none" viewBox="0 0 100 20"><path d="M0 10 Q 5 2, 10 10 T 20 10 T 30 18 T 40 4 T 50 16 T 60 6 T 70 14 T 80 8 T 90 12 T 100 10" stroke="rgba(255,255,255,0.7)" stroke-width="1.5" fill="none"/></svg>`;
        clip.appendChild(wf);
      }
      
      // Top bar (Icon + Name)
      const topBar = document.createElement('div');
      topBar.className = 'clip-top-bar';
      const iconMap = { video: '🎬', audio: '🎵', text: '🔤', effect: '✨', sticker: '🏷️' };
      const icon = iconMap[track.type] || '📦';
      topBar.innerHTML = `<span style="font-size:10px;">${icon}</span><span class="clip-title-text" title="${esc(seg.label)}">${esc(seg.label)}</span>`;
      clip.appendChild(topBar);
      
      // Bottom bar (Dur, Speed, Effects)
      const bottomBar = document.createElement('div');
      bottomBar.className = 'clip-bottom-bar';
      
      const durSecStr = (seg.duration_us / 1e6).toFixed(1) + 's';
      let badgesHtml = `<span class="clip-dur-badge">${durSecStr}</span>`;
      if (seg.speed && seg.speed !== 1.0) {
        badgesHtml += `<span class="clip-speed-badge">${seg.speed}x</span>`;
      }
      if (seg.scale && seg.scale > 1.0) {
        badgesHtml += `<span class="clip-speed-badge" style="background:rgba(234,179,8,0.5);">${seg.scale}x</span>`;
      }
      if (seg.effects && seg.effects.length > 0) {
        badgesHtml += `<span class="clip-fx-badge">✨</span>`;
      }
      bottomBar.innerHTML = badgesHtml;
      clip.appendChild(bottomBar);
      
      // Trim handles (CapCut style ║)
      const trimLeft = document.createElement('div');
      trimLeft.className = 'clip-trim-handle trim-left';
      const trimRight = document.createElement('div');
      trimRight.className = 'clip-trim-handle trim-right';
      clip.appendChild(trimLeft);
      clip.appendChild(trimRight);
      
      // Click / Razor / Drag handling
      clip.addEventListener('mousedown', (e) => {
        if (track.locked) {
          e.stopPropagation();
          return;
        }
        if (e.target.classList.contains('clip-trim-handle')) return;
        if (currentTool === 'razor') {
          e.stopPropagation();
          splitSelectedAtPlayhead(seg.id);
          return;
        }
        
        // Start Drag
        isDraggingClip = true;
        dragStartX = e.clientX;
        dragOrigStartUs = seg.start_us;
        selectClip(seg, tIdx, clip);
        
        const onMouseMove = (moveEvt) => {
          if (!isDraggingClip) return;
          const deltaX = moveEvt.clientX - dragStartX;
          const deltaUs = Math.round((deltaX / pxPerSec) * 1000000);
          const newStartUs = Math.max(0, dragOrigStartUs + deltaUs);
          clip.style.left = `${(newStartUs / 1000000) * pxPerSec}px`;
          seg.start_us = newStartUs;
          updateInspectorFields(seg);
        };
        
        const onMouseUp = async () => {
          if (isDraggingClip) {
            isDraggingClip = false;
            window.removeEventListener('mousemove', onMouseMove);
            window.removeEventListener('mouseup', onMouseUp);
            // Save to server then re-render to sync state
            await fetch('/api/update-clip', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                project_name: currentProject,
                segment_id: seg.id,
                start_us: seg.start_us
              })
            });
            // Update internal projectData to match dragged position
            for (const track of projectData.tracks) {
              for (const s2 of track.segments) {
                if (s2.id === seg.id) { s2.start_us = seg.start_us; break; }
              }
            }
          }
        };
        
        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);
      });
      
      // Left Trim Handle drag
      trimLeft.addEventListener('mousedown', (e) => {
        e.stopPropagation();
        const startX = e.clientX;
        const origStart = seg.start_us;
        const origDur = seg.duration_us;
        
        const onMove = (mv) => {
          const deltaUs = Math.round(((mv.clientX - startX) / pxPerSec) * 1000000);
          const newStart = Math.max(0, origStart + deltaUs);
          const newDur = Math.max(100000, origDur - deltaUs);
          seg.start_us = newStart;
          seg.duration_us = newDur;
          clip.style.left = `${(newStart / 1e6) * pxPerSec}px`;
          clip.style.width = `${(newDur / 1e6) * pxPerSec}px`;
        };
        
        const onUp = async () => {
          window.removeEventListener('mousemove', onMove);
          window.removeEventListener('mouseup', onUp);
          await fetch('/api/update-clip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              project_name: currentProject,
              segment_id: seg.id,
              start_us: seg.start_us,
              duration_us: seg.duration_us
            })
          });
          updateInspectorFields(seg);
        };
        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup', onUp);
      });
      
      // Right Trim Handle drag
      trimRight.addEventListener('mousedown', (e) => {
        e.stopPropagation();
        const startX = e.clientX;
        const origDur = seg.duration_us;
        
        const onMove = (mv) => {
          const deltaUs = Math.round(((mv.clientX - startX) / pxPerSec) * 1000000);
          const newDur = Math.max(100000, origDur + deltaUs);
          seg.duration_us = newDur;
          clip.style.width = `${(newDur / 1e6) * pxPerSec}px`;
        };
        
        const onUp = async () => {
          window.removeEventListener('mousemove', onMove);
          window.removeEventListener('mouseup', onUp);
          await fetch('/api/update-clip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              project_name: currentProject,
              segment_id: seg.id,
              duration_us: seg.duration_us
            })
          });
          updateInspectorFields(seg);
        };
        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup', onUp);
      });
      
      body.appendChild(clip);
    });
    
    lane.appendChild(body);
    container.appendChild(lane);
  });
}

// 5. Select Clip and Switch Inspector View
function selectClip(seg, trackIdx, clipEl) {
  document.querySelectorAll('.timeline-clip').forEach(c => c.classList.remove('selected'));
  if (clipEl) clipEl.classList.add('selected');
  
  selectedSegment = { ...seg, trackIndex: trackIdx };
  
  const crumbClip = document.getElementById('crumbCurrentClip');
  if (crumbClip && seg) crumbClip.textContent = seg.label || 'Clip';

  // Switch Center panel to Clip Inspector
  switchDetailTab('clip');
  updateInspectorFields(seg);
  
  // Sync Playhead
  updatePlayheadPosition(seg.start_us);
}

function updateInspectorFields(seg) {
  if (!seg) return;
  
  // 1. Header Info
  const typeBadge = document.getElementById('inspTypeBadge');
  const clipTitle = document.getElementById('inspClipName');
  const trackBadge = document.getElementById('inspTrackBadge');
  const timeRange = document.getElementById('inspTimeRange');
  
  const type = seg.type || 'video';
  typeBadge.textContent = type.toUpperCase();
  typeBadge.className = `insp-type-badge badge-${type}`;
  clipTitle.textContent = seg.label || 'Không tên';
  
  const tIdx = seg.trackIndex !== undefined ? seg.trackIndex : (seg.track_index !== undefined ? seg.track_index : 0);
  trackBadge.textContent = `Track ${tIdx} (${type})`;
  
  const sSec = (seg.start_us / 1e6).toFixed(2);
  const dSec = (seg.duration_us / 1e6).toFixed(2);
  const eSec = (seg.end_us ? seg.end_us / 1e6 : (seg.start_us + seg.duration_us) / 1e6).toFixed(2);
  timeRange.textContent = `${sSec}s ➔ ${eSec}s (${dSec}s)`;
  
  // 2. Sections Visibility based on Clip Type
  const textFieldWrap = document.getElementById('textFieldWrap');
  const mediaPathWrap = document.getElementById('mediaPathWrap');
  const volumeFieldWrap = document.getElementById('volumeFieldWrap');
  const speedFieldWrap = document.getElementById('speedFieldWrap');
  const scaleFieldWrap = document.getElementById('scaleFieldWrap');
  
  if (type === 'text') {
    textFieldWrap.style.display = 'flex';
    document.getElementById('inspTextInput').value = seg.details?.text || seg.label || '';
    mediaPathWrap.style.display = 'none';
    volumeFieldWrap.style.display = 'none';
    speedFieldWrap.style.display = 'none';
    scaleFieldWrap.style.display = 'none';
  } else if (type === 'video') {
    textFieldWrap.style.display = 'none';
    mediaPathWrap.style.display = 'flex';
    document.getElementById('inspMediaPath').textContent = seg.media_path || seg.details?.path || 'Chưa liên kết đường dẫn tệp';
    volumeFieldWrap.style.display = 'flex';
    speedFieldWrap.style.display = 'flex';
    scaleFieldWrap.style.display = 'flex';
  } else if (type === 'audio') {
    textFieldWrap.style.display = 'none';
    mediaPathWrap.style.display = 'flex';
    document.getElementById('inspMediaPath').textContent = seg.media_path || seg.details?.path || 'Tệp âm thanh nội bộ';
    volumeFieldWrap.style.display = 'flex';
    speedFieldWrap.style.display = 'flex';
    scaleFieldWrap.style.display = 'none';
  } else {
    // Sticker, effect, filter
    textFieldWrap.style.display = 'none';
    mediaPathWrap.style.display = 'none';
    volumeFieldWrap.style.display = 'none';
    speedFieldWrap.style.display = 'none';
    scaleFieldWrap.style.display = type === 'sticker' ? 'flex' : 'none';
  }
  
  // 3. Timings
  document.getElementById('inspStartTime').value = sSec;
  document.getElementById('inspDuration').value = dSec;
  
  // 4. Volume Slider
  const volPercent = Math.round((seg.volume !== undefined ? seg.volume : 1.0) * 100);
  const slider = document.getElementById('inspVolumeSlider');
  if (slider) slider.value = volPercent;
  const volLabel = document.getElementById('inspVolumeVal');
  if (volLabel) volLabel.textContent = `${volPercent}%`;
  
  // 5. Speed Buttons
  const curSpeed = seg.speed !== undefined ? seg.speed : 1.0;
  const speedLabel = document.getElementById('inspSpeedVal');
  if (speedLabel) speedLabel.textContent = `${curSpeed.toFixed(1)}x`;
  document.querySelectorAll('.speed-buttons .scale-btn').forEach(btn => {
    btn.classList.toggle('active', btn.textContent.includes(`${curSpeed}x`));
  });
  
  // 6. Scale Buttons
  const currentScale = seg.scale || 1.0;
  const scaleBtns = document.querySelectorAll('#scaleFieldWrap .scale-btn');
  scaleBtns.forEach(btn => btn.classList.remove('active'));
  if (currentScale >= 1.2) scaleBtns[2]?.classList.add('active');
  else if (currentScale > 1.0) scaleBtns[1]?.classList.add('active');
  else scaleBtns[0]?.classList.add('active');
  
  // 7. Applied Effects & Animations Tags
  const tagsBox = document.getElementById('inspAppliedTags');
  if (tagsBox) {
    tagsBox.innerHTML = '';
    const effects = seg.effects || [];
    const animations = seg.animations || [];
    
    if (effects.length === 0 && animations.length === 0) {
      tagsBox.innerHTML = '<span class="no-effect-hint">Không có hiệu ứng đính kèm</span>';
    } else {
      effects.forEach(eff => {
        const pill = document.createElement('span');
        pill.className = 'applied-tag-pill';
        pill.textContent = `✨ ${eff.name || eff.id || 'Hiệu ứng'}`;
        tagsBox.appendChild(pill);
      });
      animations.forEach(anim => {
        if (anim.in) {
          const pill = document.createElement('span');
          pill.className = 'applied-tag-pill';
          pill.textContent = `🎬 Vào: ${anim.in}`;
          tagsBox.appendChild(pill);
        }
        if (anim.out) {
          const pill = document.createElement('span');
          pill.className = 'applied-tag-pill';
          pill.textContent = `🎬 Ra: ${anim.out}`;
          tagsBox.appendChild(pill);
        }
      });
    }
  }
}

// Volume & Speed Handlers
async function handleVolumeChange(valPercent) {
  if (!selectedSegment) return;
  const volVal = parseFloat(valPercent) / 100;
  selectedSegment.volume = volVal;
  document.getElementById('inspVolumeVal').textContent = `${valPercent}%`;
  
  await fetch('/api/update-clip', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_name: currentProject,
      segment_id: selectedSegment.id,
      volume: volVal
    })
  });
}

async function setClipSpeed(speedVal) {
  if (!selectedSegment) return;
  selectedSegment.speed = speedVal;
  document.getElementById('inspSpeedVal').textContent = `${speedVal.toFixed(1)}x`;
  document.querySelectorAll('.speed-buttons .scale-btn').forEach(btn => {
    btn.classList.toggle('active', btn.textContent.includes(`${speedVal}x`));
  });
  
  await fetch('/api/update-clip', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_name: currentProject,
      segment_id: selectedSegment.id,
      speed: speedVal
    })
  });
}

function openClipAIPanel() {
  if (!selectedSegment) {
    showToast('Vui lòng chọn một clip trên dòng thời gian hoặc trong danh sách thành phần', 'warn');
    return;
  }
  openAIPanel();
  const prompt = `Xử lý clip "${selectedSegment.label}" (loại: ${selectedSegment.type}, bắt đầu: ${(selectedSegment.start_us/1e6).toFixed(2)}s): `;
  applyQuickPrompt(prompt);
  document.getElementById('aiPromptInput').focus();
}

// 6. Live Text Editing from Inspector
async function handleLiveTextEdit(newVal) {
  if (!selectedSegment || selectedSegment.type !== 'text') return;
  selectedSegment.label = newVal;
  document.getElementById('activeTextDisplay').textContent = newVal;
  
  // Update on timeline immediately (find text node safely)
  const clip = document.querySelector(`.timeline-clip[data-seg-id="${selectedSegment.id}"]`);
  if (clip) {
    // Find first text node and update it
    for (const node of clip.childNodes) {
      if (node.nodeType === Node.TEXT_NODE) {
        node.nodeValue = newVal;
        break;
      }
    }
  }
  
  await fetch('/api/update-clip', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_name: currentProject,
      segment_id: selectedSegment.id,
      text_content: newVal
    })
  });
}

function stepClipTime(deltaSec) {
  if (!selectedSegment) return;
  const input = document.getElementById('inspStartTime');
  input.value = Math.max(0, parseFloat(input.value) + deltaSec).toFixed(2);
  handleTimeEdit();
}

function stepClipDur(deltaSec) {
  if (!selectedSegment) return;
  const input = document.getElementById('inspDuration');
  input.value = Math.max(0.1, parseFloat(input.value) + deltaSec).toFixed(2);
  handleDurEdit();
}

async function handleTimeEdit() {
  if (!selectedSegment) return;
  const valSec = parseFloat(document.getElementById('inspStartTime').value);
  selectedSegment.start_us = Math.round(valSec * 1000000);
  renderTracks();
  
  await fetch('/api/update-clip', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_name: currentProject,
      segment_id: selectedSegment.id,
      start_us: selectedSegment.start_us
    })
  });
}

async function handleDurEdit() {
  if (!selectedSegment) return;
  const durSec = parseFloat(document.getElementById('inspDuration').value);
  selectedSegment.duration_us = Math.round(durSec * 1000000);
  renderTracks();
  
  await fetch('/api/update-clip', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_name: currentProject,
      segment_id: selectedSegment.id,
      duration_us: selectedSegment.duration_us
    })
  });
}

async function setClipScale(scaleVal) {
  if (!selectedSegment) return;
  selectedSegment.scale = scaleVal;
  updateInspectorFields(selectedSegment);
  
  await fetch('/api/update-clip', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_name: currentProject,
      segment_id: selectedSegment.id,
      scale: scaleVal
    })
  });
}

// 7. Tab Switching (Assets & Details)
function switchNavRail(tabId, el) {
  document.querySelectorAll('.rail-item').forEach(r => r.classList.remove('active'));
  if (el) el.classList.add('active');
  
  const titleMap = {
    'media': 'Footage & Video',
    'audio': 'Kho Âm Thanh & BGM',
    'text': 'Văn Bản & Phụ Đề',
    'effects': 'Kho Hiệu Ứng',
    'scanner': 'Lọc Lỗi Footage'
  };
  const titleEl = document.getElementById('assetPanelTitle');
  if (titleEl && titleMap[tabId]) titleEl.textContent = titleMap[tabId];
  
  document.querySelectorAll('.tab-pane, .asset-tab-pane').forEach(p => p.classList.remove('active'));
  const target = document.getElementById(`pane-${tabId}`);
  if (target) target.classList.add('active');
}

function switchAssetTab(tabId, clickedEl) {
  document.querySelectorAll('.asset-tab, .rail-item').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-pane, .asset-tab-pane').forEach(p => p.classList.remove('active'));
  
  // Support both direct element pass and event.currentTarget fallback
  const activeEl = clickedEl || (typeof event !== 'undefined' ? event.currentTarget : null);
  if (activeEl) activeEl.classList.add('active');
  
  const target = document.getElementById(`pane-${tabId}`);
  if (target) target.classList.add('active');

  const railBtn = document.getElementById(`rail${tabId.charAt(0).toUpperCase() + tabId.slice(1)}`);
  if (railBtn) {
    document.querySelectorAll('.rail-item').forEach(r => r.classList.remove('active'));
    railBtn.classList.add('active');
  }
}

function setCanvasAspect(aspectRatio, el) {
  document.querySelectorAll('.aspect').forEach(a => a.classList.remove('active'));
  if (el) el.classList.add('active');
  
  const preview = document.querySelector('.preview');
  if (preview) {
    if (aspectRatio === '16:9') {
      preview.style.aspectRatio = '16/9';
      preview.style.width = 'min(520px, 80%)';
    } else if (aspectRatio === '9:16') {
      preview.style.aspectRatio = '9/16';
      preview.style.width = 'min(310px, 55%)';
    } else if (aspectRatio === '1:1') {
      preview.style.aspectRatio = '1/1';
      preview.style.width = 'min(380px, 65%)';
    } else if (aspectRatio === '4:5') {
      preview.style.aspectRatio = '4/5';
      preview.style.width = 'min(340px, 60%)';
    }
  }
  showToast(`Đã chuyển tỷ lệ khung hình: ${aspectRatio}`, 'info');
}

function fitPreviewMonitor() {
  const preview = document.querySelector('.preview');
  if (preview) {
    preview.style.transform = 'none';
    showToast('Đã căn giữa vừa vặn màn hình xem trước', 'info');
  }
}

function showShortcutsHelp() {
  const modal = document.getElementById('shortcutsModal');
  if (modal) modal.classList.add('active');
}

function closeShortcutsHelp(e) {
  if (e && e.target && !e.target.classList.contains('shortcuts-modal-overlay') && !e.target.classList.contains('btn-close-modal')) return;
  const modal = document.getElementById('shortcutsModal');
  if (modal) modal.classList.remove('active');
}

function switchDetailTab(type) {
  const tabDet = document.getElementById('tabBtnDetails');
  const tabClp = document.getElementById('tabBtnClip');
  if (tabDet) tabDet.classList.toggle('selected', type === 'project');
  if (tabClp) tabClp.classList.toggle('selected', type === 'clip');
  
  const vProj = document.getElementById('viewProjectDetails');
  const vClip = document.getElementById('viewClipInspector');
  if (vProj) vProj.style.display = type === 'project' ? 'block' : 'none';
  if (vClip) vClip.style.display = type === 'clip' ? 'block' : 'none';

  if (type === 'clip' && !selectedSegment && projectData && projectData.tracks) {
    for (let tIdx = 0; tIdx < projectData.tracks.length; tIdx++) {
      const segs = projectData.tracks[tIdx].segments || [];
      if (segs.length > 0) {
        selectClip(segs[0], tIdx, null);
        break;
      }
    }
  }
}

// 8. Video Player Streaming & Playhead Sync
function getTimelineHeaderOffset() {
  const el = document.querySelector('.timeline-track-header') || document.querySelector('.track-header') || document.querySelector('.ruler-header-spacer');
  return el ? el.offsetWidth : 110;
}

function setupTimelineInteractions() {
  const container = document.getElementById('timelineScroll');
  if (!container) return;
  
  container.addEventListener('click', (e) => {
    if (isDraggingClip) return;
    const rect = container.getBoundingClientRect();
    const headerWidth = getTimelineHeaderOffset();
    const clickX = e.clientX - rect.left + container.scrollLeft - headerWidth;
    if (clickX < 0) return;
    
    const pxPerSec = PX_PER_SECOND_BASE * zoomFactor;
    const clickSec = clickX / pxPerSec;
    updatePlayheadPosition(Math.max(0, Math.round(clickSec * 1000000)));
  });
}

function updatePlayheadPosition(timeUs) {
  currentPlayheadUs = timeUs;
  const pxPerSec = PX_PER_SECOND_BASE * zoomFactor;
  const headerWidth = getTimelineHeaderOffset();
  const leftPx = headerWidth + (timeUs / 1000000) * pxPerSec;
  
  const playhead = document.getElementById('playhead');
  if (playhead) playhead.style.left = `${leftPx}px`;
  
  const tcFormatted = formatTimecode(timeUs);
  const totalUs = projectData ? (projectData.duration_us || 0) : 0;
  
  const curEl = document.getElementById('currentTimecode');
  if (curEl) curEl.textContent = tcFormatted;
  
  const previewBadge = document.getElementById('previewTimeBadge');
  if (previewBadge) {
    const totalSec = timeUs / 1000000;
    const m = Math.floor(totalSec / 60);
    const s = Math.floor(totalSec % 60);
    const ms = Math.floor((totalSec % 1) * 100);
    previewBadge.textContent = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(2, '0')}`;
  }

  const tlCur = document.getElementById('timelineCurTC');
  if (tlCur) tlCur.textContent = tcFormatted;
  
  const tlTot = document.getElementById('timelineTotTC');
  if (tlTot && totalUs) tlTot.textContent = formatTimecode(totalUs);
  
  syncPlayerMedia(timeUs);
  renderActiveBoundingBoxes(timeUs);
}

// Toolbar Functions (Zoom, Magnet, Snapping, Linkage, Tool modes)
function zoomTimelineStep(delta) {
  zoomFactor = Math.max(0.3, Math.min(3.0, zoomFactor + delta));
  const slider = document.getElementById('zoomSlider');
  if (slider) slider.value = Math.round(zoomFactor * 100);
  const durSec = (projectData?.duration_us || 0) / 1000000;
  renderRuler(durSec);
  renderTracks();
  updatePlayheadPosition(currentPlayheadUs);
}

function fitTimeline() {
  const container = document.getElementById('timelineScroll');
  if (!container || !projectData) return;
  const headerWidth = getTimelineHeaderOffset();
  const availWidth = container.clientWidth - (headerWidth + 20);
  const durSec = (projectData.duration_us || 0) / 1e6;
  if (durSec <= 0) return;
  
  zoomFactor = Math.max(0.3, Math.min(3.0, availWidth / (durSec * PX_PER_SECOND_BASE)));
  const slider = document.getElementById('zoomSlider');
  if (slider) slider.value = Math.round(zoomFactor * 100);
  
  renderRuler(durSec);
  renderTracks();
  updatePlayheadPosition(currentPlayheadUs);
}

function toggleMagnet() {
  const btn = document.getElementById('btnMagnet');
  if (btn) btn.classList.toggle('active');
}

function toggleSnapping() {
  const btn = document.getElementById('btnSnapping');
  if (btn) btn.classList.toggle('active');
}

function toggleLinkage() {
  const btn = document.getElementById('btnLinkage');
  if (btn) btn.classList.toggle('active');
}

function freezeSelected() {
  if (!selectedSegment) {
    showToast('Vui lòng chọn 1 clip để đóng băng khung hình', 'warn');
    return;
  }
  applyQuickPrompt(`Đóng băng khung hình tại ${(currentPlayheadUs/1e6).toFixed(2)}s cho clip "${selectedSegment.label}"`);
  openAIPanel();
}

function reverseSelected() {
  if (!selectedSegment) {
    showToast('Vui lòng chọn 1 clip để đảo ngược', 'warn');
    return;
  }
  applyQuickPrompt(`Đảo ngược (Reverse playback) clip "${selectedSegment.label}"`);
  openAIPanel();
}

// Preview audio player helper
function getPreviewAudioPlayer() {
  let a = document.getElementById('previewAudioPlayer');
  if (!a) {
    a = document.createElement('audio');
    a.id = 'previewAudioPlayer';
    a.preload = 'auto';
    a.style.display = 'none';
    document.body.appendChild(a);
  }
  return a;
}

let activeVideoSegment = null;

function syncPlayerMedia(timeUs) {
  if (!projectData || !projectData.tracks) return;
  const display = document.getElementById('activeTextDisplay');
  const videoPlayer = document.getElementById('mainVideoPlayer');
  const audioPlayer = getPreviewAudioPlayer();
  
  let activeText = '';
  let activeVideoPath = '';
  let videoOffsetSec = 0;
  let activeAudioPath = '';
  let audioOffsetSec = 0;
  let activeAudioVol = 1.0;
  activeVideoSegment = null;
  
  // Duyệt tracks: video tracks ưu tiên lớp trên cùng (reverse duyệt để lấy V2/V3 trên V1)
  const tracksReversed = [...projectData.tracks].reverse();
  for (const track of tracksReversed) {
    if (track.type === 'video' && !activeVideoPath) {
      for (const seg of track.segments || []) {
        if (timeUs >= seg.start_us && timeUs < seg.end_us && seg.media_path) {
          activeVideoPath = seg.media_path;
          videoOffsetSec = (timeUs - seg.start_us) / 1e6;
          activeVideoSegment = seg;
          break;
        }
      }
    }
  }
  
  // Duyệt tracks text & audio
  for (const track of projectData.tracks) {
    if (track.type === 'text') {
      for (const seg of track.segments || []) {
        if (timeUs >= seg.start_us && timeUs < seg.end_us) {
          activeText = seg.details?.text || seg.label;
          break;
        }
      }
    } else if (track.type === 'audio' && !activeAudioPath) {
      for (const seg of track.segments || []) {
        if (timeUs >= seg.start_us && timeUs < seg.end_us && seg.media_path) {
          activeAudioPath = seg.media_path;
          audioOffsetSec = (timeUs - seg.start_us) / 1e6;
          activeAudioVol = seg.volume != null ? seg.volume : 1.0;
          break;
        }
      }
    }
  }
  
  if (display) display.textContent = activeText || '';
  
  // Đồng bộ Video Player
  if (videoPlayer) {
    if (activeVideoPath) {
      const streamUrl = `/api/media?path=${encodeURIComponent(activeVideoPath)}`;
      const fullUrl = window.location.origin + streamUrl;
      if (videoPlayer.src !== fullUrl) {
        videoPlayer.src = streamUrl;
        videoPlayer.currentTime = videoOffsetSec;
        if (isPlaying) videoPlayer.play().catch(() => {});
      } else {
        if (Math.abs(videoPlayer.currentTime - videoOffsetSec) > 0.25) {
          videoPlayer.currentTime = videoOffsetSec;
        }
      }
      videoPlayer.style.display = 'block';
    } else {
      // Khi không có video tại playhead, vẫn giữ khung hình mờ thay vì tắt phụt
      if (videoPlayer.paused) {
        // Giữ nguyên frame
      } else {
        videoPlayer.pause();
      }
    }
  }
  
  // Đồng bộ Audio Player
  if (audioPlayer) {
    if (activeAudioPath) {
      const audioUrl = `/api/media?path=${encodeURIComponent(activeAudioPath)}`;
      const fullAudioUrl = window.location.origin + audioUrl;
      audioPlayer.volume = Math.max(0.0, Math.min(1.0, activeAudioVol));
      if (audioPlayer.src !== fullAudioUrl) {
        audioPlayer.src = audioUrl;
        audioPlayer.currentTime = audioOffsetSec;
        if (isPlaying) audioPlayer.play().catch(() => {});
      } else {
        if (Math.abs(audioPlayer.currentTime - audioOffsetSec) > 0.3) {
          audioPlayer.currentTime = audioOffsetSec;
        }
      }
    } else {
      if (!audioPlayer.paused) audioPlayer.pause();
    }
  }
}

function playLoop(timestamp) {
  if (!isPlaying) return;
  if (!playStartTime) playStartTime = timestamp;
  const elapsedMs = timestamp - playStartTime;
  const totalUs = projectData ? (projectData.duration_us || 0) : 0;
  
  const videoPlayer = document.getElementById('mainVideoPlayer');
  let currentUs;
  if (videoPlayer && !videoPlayer.paused && videoPlayer.duration > 0 && activeVideoSegment) {
    currentUs = activeVideoSegment.start_us + Math.round(videoPlayer.currentTime * 1e6);
  } else {
    currentUs = playStartUs + Math.round(elapsedMs * 1000);
  }
  
  if (totalUs > 0 && currentUs >= totalUs) {
    updatePlayheadPosition(0);
    togglePlay();
    return;
  }
  
  updatePlayheadPosition(currentUs);
  playAnimFrameId = requestAnimationFrame(playLoop);
}

function togglePlay() {
  isPlaying = !isPlaying;
  const btn = document.getElementById('playBtn');
  const videoPlayer = document.getElementById('mainVideoPlayer');
  const audioPlayer = getPreviewAudioPlayer();
  
  if (isPlaying) {
    if (btn) btn.textContent = '⏸';
    playStartTime = 0;
    playStartUs = currentPlayheadUs;
    if (videoPlayer && videoPlayer.src) videoPlayer.play().catch(() => {});
    if (audioPlayer && audioPlayer.src) audioPlayer.play().catch(() => {});
    playAnimFrameId = requestAnimationFrame(playLoop);
  } else {
    if (btn) btn.textContent = '▶';
    if (playAnimFrameId) cancelAnimationFrame(playAnimFrameId);
    playAnimFrameId = null;
    if (videoPlayer) videoPlayer.pause();
    if (audioPlayer) audioPlayer.pause();
  }
}

// 9. Split and Delete Operations với cơ chế chống bấm đúp
let isOperationPending = false;

async function splitSelectedAtPlayhead(targetId) {
  if (isOperationPending) return;
  let segId = targetId || (selectedSegment ? selectedSegment.id : null);
  
  // Tự động tìm segment tại playhead nếu chưa chọn
  if (!segId && projectData && projectData.tracks) {
    for (const t of projectData.tracks) {
      for (const s of t.segments || []) {
        if (currentPlayheadUs > s.start_us && currentPlayheadUs < s.end_us) {
          segId = s.id;
          selectedSegment = s;
          break;
        }
      }
      if (segId) break;
    }
  }
  
  if (!segId) {
    showToast('Vui lòng chọn 1 clip hoặc đặt playhead trên clip để cắt đôi', 'warn');
    return;
  }
  
  isOperationPending = true;
  try {
    const res = await fetch('/api/split-clip', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_name: currentProject,
        command: 'split',
        target_segment_id: segId,
        playhead_time_us: currentPlayheadUs
      })
    });
    if (res.status === 409) {
      showToast('CapCut đang mở — chỉnh sửa bị khóa', 'error');
      const banner = document.getElementById('capcutStatusBanner');
      if (banner) banner.style.display = 'flex';
      return;
    }
    const data = await res.json();
    if (res.ok && data.status === 'success') {
      showToast(data.message || 'Đã cắt clip thành công', 'success');
      const scrollEl = document.getElementById('timelineScroll');
      const savedScrollLeft = scrollEl ? scrollEl.scrollLeft : 0;
      const targetSegId = segId;
      await loadProject(currentProject, true);
      if (scrollEl) {
        scrollEl.scrollLeft = savedScrollLeft;
        requestAnimationFrame(() => { scrollEl.scrollLeft = savedScrollLeft; });
      }
      // Giữ selection cho segment vừa cắt
      if (projectData && projectData.tracks) {
        let foundSeg = null;
        let foundTIdx = 0;
        for (let tIdx = 0; tIdx < projectData.tracks.length; tIdx++) {
          const s = (projectData.tracks[tIdx].segments || []).find(seg => seg.id === targetSegId || seg.id === data.new_segment_id);
          if (s) { foundSeg = s; foundTIdx = tIdx; break; }
        }
        if (foundSeg) {
          const clipEl = document.querySelector(`.timeline-clip[data-seg-id="${foundSeg.id}"]`);
          selectClip(foundSeg, foundTIdx, clipEl);
        }
      }
    } else {
      showToast(data.message || data.detail || 'Không thể cắt clip', 'error');
    }
  } catch (e) {
    showToast(`Lỗi khi cắt clip: ${e.message}`, 'error');
  } finally {
    isOperationPending = false;
  }
}

async function deleteSelected() {
  if (isOperationPending) return;
  if (!selectedSegment) {
    showToast('Vui lòng chọn 1 clip để xóa', 'warn');
    return;
  }
  const segId = selectedSegment.id;
  const clipLabel = selectedSegment.label || 'Clip';
  
  isOperationPending = true;
  try {
    const res = await fetch('/api/delete-clip', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_name: currentProject,
        command: 'delete',
        target_segment_id: segId
      })
    });
    if (res.status === 409) {
      showToast('CapCut đang mở — chỉnh sửa bị khóa', 'error');
      const banner = document.getElementById('capcutStatusBanner');
      if (banner) banner.style.display = 'flex';
      return;
    }
    const data = await res.json();
    if (res.ok && data.status === 'success') {
      const scrollEl = document.getElementById('timelineScroll');
      const savedScrollLeft = scrollEl ? scrollEl.scrollLeft : 0;
      selectedSegment = null;
      switchDetailTab('project');
      await loadProject(currentProject, true);
      if (scrollEl) {
        scrollEl.scrollLeft = savedScrollLeft;
        requestAnimationFrame(() => { scrollEl.scrollLeft = savedScrollLeft; });
      }
      // Hiển thị toast kèm nút Hoàn tác trong 6 giây theo mục 4.5
      showToast(`Đã xóa "${clipLabel}"`, 'info', 'Hoàn tác', undoAction, 6000);
    } else {
      showToast(data.message || data.detail || 'Không thể xóa clip', 'error');
    }
  } catch (e) {
    showToast(`Lỗi xóa clip: ${e.message}`, 'error');
  } finally {
    isOperationPending = false;
  }
}

// 9b. Undo & Redo & Duplicate operations
async function undoAction() {
  if (isOperationPending) return;
  isOperationPending = true;
  try {
    const res = await fetch(`/api/undo/${encodeURIComponent(currentProject)}`, { method: 'POST' });
    const data = await res.json();
    if (res.ok && data.status === 'success') {
      await loadProject(currentProject, true);
      showToast(data.message || 'Đã hoàn tác thao tác', 'success');
    } else {
      showToast(data.message || data.detail || 'Không có lịch sử để hoàn tác', 'warn');
    }
  } catch (e) {
    showToast(`Lỗi hoàn tác: ${e.message}`, 'error');
  } finally {
    isOperationPending = false;
  }
}

async function redoAction() {
  if (isOperationPending) return;
  isOperationPending = true;
  try {
    const res = await fetch(`/api/redo/${encodeURIComponent(currentProject)}`, { method: 'POST' });
    const data = await res.json();
    if (res.ok && data.status === 'success') {
      await loadProject(currentProject, true);
      showToast(data.message || 'Đã làm lại thao tác', 'success');
    } else {
      showToast(data.message || data.detail || 'Đã ở trạng thái mới nhất', 'info');
    }
  } catch (e) {
    showToast(`Lỗi làm lại: ${e.message}`, 'error');
  } finally {
    isOperationPending = false;
  }
}

function addNewTrack() {
  showToast('Thêm track: Hãy thêm track trực tiếp trong CapCut Desktop rồi tải lại trang.', 'info');
}

async function duplicateSelected() {
  if (isOperationPending) return;
  if (!selectedSegment) {
    showToast('Vui lòng chọn 1 clip để nhân đôi', 'warn');
    return;
  }
  const prompt = `Nhân đôi clip "${selectedSegment.label}" (tại ${(selectedSegment.end_us/1e6).toFixed(2)}s)`;
  showToast(`Đang nhân đôi "${selectedSegment.label}"...`, 'info');
  isOperationPending = true;
  try {
    const res = await fetch('/api/execute-command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_name: currentProject,
        command: prompt,
        target_segment_id: selectedSegment.id
      })
    });
    const data = await res.json();
    if (res.ok && data.status === 'success') {
      showToast('Đã nhân đôi clip thành công', 'success');
      await loadProject(currentProject, true);
    }
  } catch (e) {
    showToast(`Lỗi nhân đôi: ${e.message}`, 'error');
  } finally {
    isOperationPending = false;
  }
}

// 10. Quality Gate Audit Modal
async function openQAModal() {
  const modal = document.getElementById('qaModal');
  modal.classList.add('open');
  trapModalFocus(modal);
  
  try {
    const res = await fetch(`/api/quality-audit/${currentProject}`);
    const data = await res.json();
    
    const dial = document.getElementById('qaScoreDial');
    dial.textContent = data.score;
    dial.style.borderColor = data.score >= 80 ? '#10b981' : (data.score >= 60 ? '#f59e0b' : '#ef4444');
    dial.style.color = dial.style.borderColor;
    
    document.getElementById('qaScoreStatus').textContent = data.status === 'PASS' ? 'ĐẠT CHUẨN (PASS)' : 'CẦN TỐI ƯU (WARNING)';
    document.getElementById('qaScoreStatus').style.color = dial.style.borderColor;
    
    const list = document.getElementById('qaIssuesList');
    list.innerHTML = '';
    
    if (data.issues.length === 0) {
      list.innerHTML = '<div style="color: #10b981; text-align: center; padding: 20px;">✓ Không phát hiện lỗi chất lượng nào! Video đã đạt chuẩn thương mại.</div>';
    } else {
      data.issues.forEach(iss => {
        const item = document.createElement('div');
        item.className = 'qa-issue-item';
        item.innerHTML = `
          <div class="qa-issue-header">
            <span class="issue-type">${esc(iss.type)}</span>
            <span class="issue-badge">${esc(iss.severity)}</span>
          </div>
          <div class="issue-msg">${esc(iss.message)}</div>
          <div class="issue-action">Đề xuất: ${esc(iss.fix_action)}</div>
        `;
        list.appendChild(item);
      });
    }
  } catch (err) {
    console.error('Audit failed:', err);
    showToast(`Lỗi kiểm định chất lượng: ${err.message || 'Không thể kết nối máy chủ'}`, 'error');
  }
}

function closeQAModal(e) {
  // Allow calling from overlay click OR directly
  document.getElementById('qaModal').classList.remove('open');
  releaseModalFocus();
}

async function autoFixAllQuality() {
  closeQAModal();
  applyQuickPrompt("Tối ưu toàn bộ chất lượng: Kéo phụ đề về Safe zone y=-0.404, triệt tiêu đuôi chết và áp dụng Montserrat Shadow");
  openAIPanel();
  await executeAICommand();
}

// 11. Presets Insertion
async function insertTextPreset(text, color) {
  applyQuickPrompt(`Thêm chữ mới "${text}" màu ${color} tại vị trí playhead`);
  openAIPanel();
  await executeAICommand();
}

async function applyEffectToSelected(effectName, paramKey) {
  if (!selectedSegment) {
    showToast('Vui lòng chọn 1 clip trên timeline trước khi áp dụng hiệu ứng', 'warn');
    return;
  }
  applyQuickPrompt(`Áp dụng hiệu ứng "${effectName}" cho clip được chọn với thông số ${paramKey}`);
  openAIPanel();
  await executeAICommand();
}

async function applyTransition(transName, durUs) {
  applyQuickPrompt(`Chèn chuyển cảnh "${transName}" thời lượng ${(durUs/1e6).toFixed(2)}s tại điểm cắt`);
  openAIPanel();
  await executeAICommand();
}

function handleColorAdjust(type, val) {
  document.getElementById(`val-${type}`).textContent = val;
  const canvas = document.getElementById('playerCanvas');
  if (type === 'brightness') canvas.style.filter = `brightness(${1 + val/100})`;
  else if (type === 'contrast') canvas.style.filter = `contrast(${1 + val/100})`;
  else if (type === 'saturation') canvas.style.filter = `saturate(${1 + val/100})`;
}

// Render media thumbnails hiện đại chuẩn Studio
function renderMediaTab() {
  const grid = document.getElementById('mediaGrid');
  if (!grid) return;
  grid.innerHTML = '';
  if (!projectData) return;
  
  let mediaFound = 0;
  projectData.tracks.forEach((t, tIdx) => {
    (t.segments || []).forEach(s => {
      if (s.media_path) {
        mediaFound++;
        const card = document.createElement('div');
        card.className = 'media-card';
        
        const ext = (s.media_path.split('.').pop() || 'mp4').toUpperCase();
        const isVideo = ['MP4', 'MOV', 'AVI', 'MKV', 'WEBM'].includes(ext);
        const streamUrl = `/api/media?path=${encodeURIComponent(s.media_path)}`;
        const durSec = ((s.end_us - s.start_us) / 1e6).toFixed(1);
        
        card.innerHTML = `
          <div class="media-thumb">
            ${isVideo
              ? `<video src="${streamUrl}" preload="metadata" muted class="thumb-video" onloadedmetadata="this.currentTime=1" onerror="this.style.display='none'; if(this.nextElementSibling) this.nextElementSibling.style.display='flex';"></video>
                 <div class="thumb-fallback" style="display:none;">🎬</div>`
              : `<img src="${streamUrl}" class="thumb-img" onerror="this.style.display='none'; if(this.nextElementSibling) this.nextElementSibling.style.display='flex';" />
                 <div class="thumb-fallback" style="display:none;">🖼️</div>`
            }
            <div class="media-play-overlay">▶</div>
            <span class="media-badge-dur">${durSec}s</span>
            <span class="media-badge-ext">${esc(ext)}</span>
          </div>
          <div class="media-info-row">
            <div class="media-name" title="${esc(s.label)}">${esc(s.label)}</div>
            <div class="media-meta">Track ${tIdx + 1}</div>
          </div>
        `;
        card.onclick = () => {
          updatePlayheadPosition(s.start_us);
          selectClip(s, tIdx);
        };
        grid.appendChild(card);
      }
    });
  });
  
  if (mediaFound === 0) {
    grid.innerHTML = `
      <div class="empty-media-box">
        <div class="empty-media-icon">🎬</div>
        <div class="empty-media-title">Chưa có footage video</div>
        <div class="empty-media-sub">Dự án hiện tại gồm các lớp Text và Hiệu ứng. Kéo thả tệp video vào timeline để bắt đầu.</div>
      </div>
    `;
  }
}

// 12. AI Modal & Execution
function openAIPanel() {
  const modal = document.getElementById('aiModal');
  modal.classList.add('open');
  trapModalFocus(modal);
  const segName = selectedSegment ? selectedSegment.label : 'Toàn bộ Timeline';
  const segTime = selectedSegment ? `${(selectedSegment.start_us/1e6).toFixed(2)}s ➔ ${(selectedSegment.end_us/1e6).toFixed(2)}s` : '00:00 - Hết';
  const trackName = selectedSegment ? `Track ${selectedSegment.trackIndex} (${selectedSegment.type})` : 'Tất cả các Track';
  
  document.getElementById('ctxSegName').textContent = segName;
  document.getElementById('ctxSegTime').textContent = segTime;
  document.getElementById('ctxTrackName').textContent = trackName;
  document.getElementById('aiStatusMsg').textContent = '';
}

function closeAIPanel() {
  document.getElementById('aiModal').classList.remove('open');
  releaseModalFocus();
}

function applyQuickPrompt(text) {
  document.getElementById('aiPromptInput').value = text;
}

async function executeAICommand() {
  const prompt = document.getElementById('aiPromptInput').value.trim();
  if (!prompt) return;
  
  const statusEl = document.getElementById('aiStatusMsg');
  statusEl.style.color = '#00e5ff';
  statusEl.textContent = '⏳ Đang thực thi qua Antigravity MCP...';
  
  try {
    const payload = {
      project_name: currentProject,
      command: prompt,
      target_segment_id: selectedSegment ? selectedSegment.id : null,
      target_track_index: selectedSegment ? selectedSegment.trackIndex : null,
      playhead_time_us: currentPlayheadUs
    };
    
    const res = await fetch('/api/execute-command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    const result = await res.json();
    if (result.status === 'success') {
      statusEl.style.color = '#10b981';
      statusEl.textContent = result.feedback || '✓ Đã cập nhật thành công!';
      setTimeout(async () => {
        await loadProject(currentProject);
        setTimeout(() => closeAIPanel(), 1200);
      }, 500);
    } else {
      statusEl.style.color = '#ef4444';
      statusEl.textContent = '❌ Lỗi: ' + (result.detail || 'Không thể thực thi');
    }
  } catch (err) {
    statusEl.style.color = '#ef4444';
    statusEl.textContent = '❌ Lỗi server: ' + err.message;
  }
}

// 13. Tools & Keyboard shortcuts
function setTool(toolName) {
  currentTool = toolName;
  document.getElementById('toolSelect').classList.toggle('active', toolName === 'select');
  document.getElementById('toolRazor').classList.toggle('active', toolName === 'razor');
}

function handleZoom(val) {
  zoomFactor = val / 100;
  if (projectData) {
    renderRuler(projectData.duration_us / 1e6);
    renderTracks();
    updatePlayheadPosition(currentPlayheadUs);
  }
}

function fitTimeline() {
  handleZoom(100);
  document.getElementById('zoomSlider').value = 100;
}

function toggleSafeGuide() {
  const guide = document.getElementById('tiktokSafeGuide');
  guide.style.display = guide.style.display === 'none' ? 'flex' : 'none';
}

function formatTimecode(us) {
  const totalSec = us / 1000000;
  const hours = Math.floor(totalSec / 3600).toString().padStart(2, '0');
  const minutes = Math.floor((totalSec % 3600) / 60).toString().padStart(2, '0');
  const seconds = Math.floor(totalSec % 60).toString().padStart(2, '0');
  const fps = projectData?.fps || 30;
  const frames = Math.floor((totalSec % 1) * fps).toString().padStart(2, '0');
  return `${hours}:${minutes}:${seconds}:${frames}`;
}

// Quản lý Modal Focus Trap (WCAG A11y)
let prevActiveElementBeforeModal = null;

function trapModalFocus(modalEl) {
  if (!modalEl) return;
  prevActiveElementBeforeModal = document.activeElement;
  const focusables = modalEl.querySelectorAll('button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])');
  if (focusables.length > 0) {
    setTimeout(() => focusables[0].focus(), 50);
  }
}

function releaseModalFocus() {
  if (prevActiveElementBeforeModal && typeof prevActiveElementBeforeModal.focus === 'function') {
    prevActiveElementBeforeModal.focus();
    prevActiveElementBeforeModal = null;
  }
}

function closeAllModals() {
  const modals = document.querySelectorAll('.qa-modal-overlay, .ai-modal-overlay, .mcp-modal-overlay, .agent-cockpit-overlay');
  modals.forEach(m => m.classList.remove('open', 'active'));
  releaseModalFocus();
}

function setupKeyboardShortcuts() {
  window.addEventListener('keydown', (e) => {
    const target = e.target;
    const isInput = ['INPUT', 'TEXTAREA', 'SELECT'].includes(target?.tagName) || target?.isContentEditable;
    const activeModal = document.querySelector('.qa-modal-overlay.open, .ai-modal-overlay.open, .mcp-modal-overlay.open, .mcp-modal-overlay.active, .agent-cockpit-overlay.open');
    
    // Xử lý Focus Trap bằng phím Tab khi modal đang mở
    if (activeModal && e.key === 'Tab') {
      const focusables = Array.from(activeModal.querySelectorAll('button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'));
      if (focusables.length > 0) {
        const firstEl = focusables[0];
        const lastEl = focusables[focusables.length - 1];
        if (e.shiftKey) {
          if (document.activeElement === firstEl || !activeModal.contains(document.activeElement)) {
            e.preventDefault();
            lastEl.focus();
          }
        } else {
          if (document.activeElement === lastEl || !activeModal.contains(document.activeElement)) {
            e.preventDefault();
            firstEl.focus();
          }
        }
        return;
      }
    }

    // Nếu modal đang mở hoặc đang gõ input: Esc đóng modal / blur input
    if (e.key === 'Escape') {
      if (activeModal) {
        e.preventDefault();
        closeAllModals();
        return;
      }
      if (isInput) {
        target.blur();
        return;
      }
      // Bỏ chọn clip
      if (selectedSegment) {
        selectedSegment = null;
        switchDetailTab('project');
        renderTracks();
      }
      return;
    }
    
    // Bỏ qua tất cả các phím tắt khác khi đang gõ vào input/textarea/select hoặc khi modal mở
    if (isInput || activeModal) return;
    
    // Space: Phát / Dừng
    if (e.code === 'Space') {
      e.preventDefault();
      togglePlay();
      return;
    }
    
    // Ctrl+B: Cắt đôi tại playhead (Phải kiểm tra ctrl trước B)
    if ((e.ctrlKey || e.metaKey) && (e.key === 'b' || e.key === 'B')) {
      e.preventDefault();
      splitSelectedAtPlayhead();
      return;
    }
    
    // V: Chuyển sang công cụ chọn
    if ((e.key === 'v' || e.key === 'V') && !e.ctrlKey && !e.metaKey) {
      setTool('select');
      return;
    }
    
    // B: Chuyển sang dao lam (Razor)
    if ((e.key === 'b' || e.key === 'B') && !e.ctrlKey && !e.metaKey) {
      setTool('razor');
      return;
    }
    
    // Delete / Backspace: Xóa clip đã chọn
    if (e.key === 'Delete' || e.key === 'Backspace') {
      e.preventDefault();
      deleteSelected();
      return;
    }
    
    // Ctrl+Shift+Z hoặc Ctrl+Y: Redo (Làm lại)
    if ((e.ctrlKey || e.metaKey) && ((e.shiftKey && (e.key === 'z' || e.key === 'Z')) || e.key === 'y' || e.key === 'Y')) {
      e.preventDefault();
      redoAction();
      return;
    }
    
    // Ctrl+Z: Undo (Hoàn tác)
    if ((e.ctrlKey || e.metaKey) && (e.key === 'z' || e.key === 'Z')) {
      e.preventDefault();
      undoAction();
      return;
    }
    
    // Ctrl+D: Nhân đôi clip đã chọn
    if ((e.ctrlKey || e.metaKey) && (e.key === 'd' || e.key === 'D')) {
      e.preventDefault();
      duplicateSelected();
      return;
    }
    
    // ← / →: Lùi / tiến 1 frame theo fps thật của project
    // Shift + ← / →: Lùi / tiến 1 giây
    const fps = projectData?.fps || 30;
    const oneFrameUs = Math.round(1000000 / fps);
    const stepUs = e.shiftKey ? 1000000 : oneFrameUs;
    const totalUs = projectData?.duration_us || 0;
    
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      updatePlayheadPosition(Math.max(0, currentPlayheadUs - stepUs));
      return;
    }
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      updatePlayheadPosition(Math.min(totalUs, currentPlayheadUs + stepUs));
      return;
    }
  });
}

/* ==========================================================================
   AI AGENT REALTIME EDIT & FOOTAGE ERROR BOUNDING BOX ENGINE
   ========================================================================== */

// 14. Scan Project Footage & Timeline Errors
async function scanCurrentProjectErrors() {
  const container = document.getElementById('errorItemsContainer');
  if (!container) return;
  
  try {
    const res = await fetch(`/api/scan-footage-errors/${currentProject}`);
    const data = await res.json();
    
    detectedErrors = data.errors || [];
    
    // Update header & tab badges
    const totalCount = detectedErrors.length;
    const headerBadge = document.getElementById('headerErrCount');
    if (headerBadge) headerBadge.textContent = totalCount;
    
    const tabBadge = document.getElementById('tabErrBadge');
    if (tabBadge) {
      tabBadge.textContent = totalCount;
      tabBadge.style.display = totalCount > 0 ? 'inline-block' : 'none';
    }
    
    // Update Scanner Top Card
    const scoreDial = document.getElementById('scannerScoreDial');
    if (scoreDial) {
      scoreDial.textContent = data.health_score || 85;
      const col = data.health_score >= 85 ? '#10b981' : (data.health_score >= 60 ? '#f59e0b' : '#ef4444');
      scoreDial.style.borderColor = col;
      scoreDial.style.color = col;
    }
    
    const statusTitle = document.getElementById('scannerStatusTitle');
    if (statusTitle) {
      if (totalCount === 0) {
        statusTitle.textContent = '✓ Timeline & Footage Chuẩn 100%';
        statusTitle.style.color = '#10b981';
      } else {
        statusTitle.textContent = `Phát hiện ${totalCount} vùng cần tối ưu`;
        statusTitle.style.color = '#f59e0b';
      }
    }
    
    const subStats = document.getElementById('scannerSubStats');
    if (subStats) {
      subStats.textContent = `${data.critical_count} lỗi nghiêm trọng · ${data.warning_count} cảnh báo viền/safe zone`;
    }
    
    // Update filter counts
    const safeCount = detectedErrors.filter(e => e.category === 'safe_zone').length;
    const framingCount = detectedErrors.filter(e => e.category === 'framing').length;
    const pacingCount = detectedErrors.filter(e => e.category === 'pacing').length;
    const typoCount = detectedErrors.filter(e => e.category === 'typography').length;
    
    const fAll = document.getElementById('filterAllCount'); if (fAll) fAll.textContent = totalCount;
    const fSafe = document.getElementById('filterSafeCount'); if (fSafe) fSafe.textContent = safeCount;
    const fFraming = document.getElementById('filterFramingCount'); if (fFraming) fFraming.textContent = framingCount;
    const fPacing = document.getElementById('filterPacingCount'); if (fPacing) fPacing.textContent = pacingCount;
    const fTypo = document.getElementById('filterTypoCount'); if (fTypo) fTypo.textContent = typoCount;
    
    // Update Cockpit modal counters
    updateCockpitMetrics(data);
    
    // Render Error List & Timeline Markers
    renderErrorList(currentErrorFilter);
    renderTimelineErrorMarkers();
    renderActiveBoundingBoxes(currentPlayheadUs);
    
  } catch (err) {
    console.error('Scan footage errors failed:', err);
    if (container) {
      container.innerHTML = `<div style="color:#ef4444;font-size:11px;padding:12px;text-align:center;">Lỗi quét footage: ${esc(err.message)}</div>`;
    }
  }
}

function filterErrorList(category, clickedEl) {
  currentErrorFilter = category;
  document.querySelectorAll('.err-chip').forEach(c => c.classList.remove('active'));
  if (clickedEl) clickedEl.classList.add('active');
  renderErrorList(category);
}

function renderErrorList(category = 'all') {
  const container = document.getElementById('errorItemsContainer');
  if (!container) return;
  container.innerHTML = '';
  
  const filtered = detectedErrors.filter(err => {
    if (category === 'all') return true;
    return err.category === category;
  });
  
  if (filtered.length === 0) {
    container.innerHTML = `
      <div style="color: var(--color-success); font-size: 11px; padding: 24px 12px; text-align: center; background: var(--bg-surface); border-radius: var(--radius-md); border: 1px dashed var(--border-medium);">
        <div style="font-size: 20px; margin-bottom: 6px;">✓</div>
        <strong>Không có lỗi nào thuộc danh mục này!</strong>
        <div style="color: var(--text-muted); font-size: 11px; margin-top: 4px;">Footage & timeline đạt chuẩn thương mại.</div>
      </div>
    `;
    return;
  }
  
  // Gộp các lỗi theo Rule / Tên nhóm chính (ví dụ gom 25 lỗi Safe zone thành 1 nhóm)
  const groups = {};
  filtered.forEach(err => {
    const isFixed = agentFixedIds.has(err.id) || err.fixed;
    const groupKey = err.rule_id || err.title || err.category;
    if (!groups[groupKey]) {
      groups[groupKey] = {
        title: err.title,
        category: err.category,
        severity: err.severity,
        items: []
      };
    }
    if (err.severity === 'CRITICAL') groups[groupKey].severity = 'CRITICAL';
    groups[groupKey].items.push({ ...err, isFixed });
  });

  Object.values(groups).forEach(grp => {
    const card = document.createElement('div');
    card.className = 'err-group-card';
    const totalInGroup = grp.items.length;
    const unfixedItems = grp.items.filter(i => !i.isFixed);
    const unfixedCount = unfixedItems.length;
    const sevClass = (grp.severity || 'info').toLowerCase();

    card.innerHTML = `
      <div class="err-group-header">
        <div class="err-group-left">
          <span class="severity-dot ${sevClass}" title="${esc(grp.severity)}"></span>
          <div>
            <div class="err-group-title">${esc(grp.title)}</div>
            <div class="err-group-count">${totalInGroup} vị trí · ${unfixedCount > 0 ? `Cần sửa ${unfixedCount}` : '✓ Đã sửa xong'}</div>
          </div>
        </div>
        ${unfixedCount > 0 ? `<button class="btn-fix-all-group" type="button">⚡ Sửa tất cả (${totalInGroup})</button>` : `<span style="color:var(--color-success);font-size:11px;font-weight:600;">✓ Đã tối ưu</span>`}
      </div>
      <div class="err-group-items" style="display: flex;">
        ${grp.items.map(item => `
          <div class="err-single-row" data-err-id="${esc(item.id)}" data-time="${item.target_time_us || item.start_us}" data-seg-id="${esc(item.segment_id || '')}">
            <span class="err-row-time">${formatTimecode(item.start_us)}</span>
            <span class="err-row-desc" title="${esc(item.description)}">${esc(item.description)}</span>
            ${!item.isFixed ? `<button class="btn-fix-single" type="button" data-fix-id="${esc(item.id)}">Sửa</button>` : `<span style="color:var(--color-success);font-size:10px;">✓</span>`}
          </div>
        `).join('')}
      </div>
    `;

    // Toggle accordion
    const headerEl = card.querySelector('.err-group-header');
    const itemsEl = card.querySelector('.err-group-items');
    headerEl.addEventListener('click', () => {
      itemsEl.style.display = itemsEl.style.display === 'none' ? 'flex' : 'none';
    });

    // Button fix all group
    const fixAllBtn = card.querySelector('.btn-fix-all-group');
    if (fixAllBtn) {
      fixAllBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        fixEntireErrorGroup(grp.title);
      });
    }

    // Single item clicks
    card.querySelectorAll('.err-single-row').forEach(row => {
      row.addEventListener('click', () => {
        const eid = row.getAttribute('data-err-id');
        const t = parseInt(row.getAttribute('data-time'), 10) || 0;
        const sid = row.getAttribute('data-seg-id') || '';
        seekAndHighlightError(eid, t, sid);
      });
    });

    // Button fix single item
    card.querySelectorAll('.btn-fix-single').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const fixId = btn.getAttribute('data-fix-id');
        if (fixId) executeSingleAutoFix(fixId);
      });
    });

    container.appendChild(card);
  });
}

// Sửa tất cả lỗi trong 1 nhóm
async function fixEntireErrorGroup(groupTitle) {
  const matches = detectedErrors.filter(e => e.title === groupTitle && !agentFixedIds.has(e.id) && !e.fixed);
  if (matches.length === 0) {
    showToast('Tất cả vị trí trong nhóm này đã được xử lý xong', 'info');
    return;
  }
  showToast(`Đang tự động sửa ${matches.length} vị trí...`, 'info');
  for (const m of matches) {
    await executeSingleAutoFix(m.id);
  }
  showToast(`✓ Đã tối ưu xong ${matches.length} vị trí`, 'success');
  renderErrorList(currentErrorFilter);
}

// Nhảy playhead đến lỗi và khoanh vùng
function seekAndHighlightError(errId, timeUs, segId) {
  updatePlayheadPosition(timeUs);
  if (segId) {
    const segEl = document.querySelector(`.timeline-clip[data-seg-id="${segId}"]`);
    if (segEl) {
      document.querySelectorAll('.timeline-clip').forEach(c => c.classList.remove('selected'));
      segEl.classList.add('selected');
    }
  }
  flashBoundingBox(errId);
}

// 15. Real-time Bounding Box Canvas Overlay (ROI Khoanh Vùng)
function renderActiveBoundingBoxes(timeUs) {
  const container = document.getElementById('errorBBoxLayer');
  if (!container) return;
  
  if (!showBBoxOverlay) {
    container.innerHTML = '';
    return;
  }
  
  // Tìm lỗi tại thời điểm playhead
  const activeErrors = detectedErrors.filter(err => {
    const s = err.start_us - 100_000;
    const e = err.end_us + 100_000;
    return timeUs >= s && timeUs <= e;
  });
  
  container.innerHTML = '';
  
  activeErrors.forEach(err => {
    const isFixed = agentFixedIds.has(err.id) || err.fixed;
    const b = err.bbox || { left: 10, top: 20, width: 80, height: 20 };
    
    const boxEl = document.createElement('div');
    boxEl.id = `bbox_${err.id}`;
    boxEl.className = `error-bbox ${isFixed ? 'is-fixed' : ''}`;
    boxEl.style.left = `${b.left}%`;
    boxEl.style.top = `${b.top}%`;
    boxEl.style.width = `${b.width}%`;
    boxEl.style.height = `${b.height}%`;
    
    boxEl.innerHTML = `
      <div class="error-bbox-tag">${esc(err.title.slice(0, 28))}</div>
    `;
    
    boxEl.onclick = (e) => {
      e.stopPropagation();
      if (!isFixed) {
        executeSingleAutoFix(err.id);
      }
    };
    
    container.appendChild(boxEl);
  });
}

function flashBoundingBox(errId) {
  const bEl = document.getElementById(`bbox_${errId}`);
  if (bEl) {
    bEl.style.transform = 'scale(1.04)';
    bEl.style.borderColor = '#ffffff';
    setTimeout(() => {
      if (bEl) {
        bEl.style.transform = '';
        bEl.style.borderColor = '';
      }
    }, 450);
  }
}

function toggleBBoxOverlay() {
  const chk = document.getElementById('btnToggleBBox');
  showBBoxOverlay = chk ? chk.checked : !showBBoxOverlay;
  renderActiveBoundingBoxes(currentPlayheadUs);
}

function toggleSafeGuide() {
  const guide = document.getElementById('tiktokSafeGuide');
  const chk = document.getElementById('btnToggleSafeGuide');
  const isVis = chk ? chk.checked : !guide.classList.contains('visible');
  if (guide) guide.classList.toggle('visible', isVis);
}

// 16. Timeline Ruler Error Markers: Nhỏ 6px nằm ở lane riêng dưới thước số
function renderTimelineErrorMarkers() {
  const lane = document.getElementById('rulerMarkerLane') || document.getElementById('rulerTrack');
  if (!lane) return;
  lane.innerHTML = '';
  
  const pxPerSec = PX_PER_SECOND_BASE * zoomFactor;
  detectedErrors.forEach(err => {
    const isFixed = agentFixedIds.has(err.id) || err.fixed;
    if (isFixed) return;
    
    const timeSec = err.start_us / 1e6;
    const leftPx = timeSec * pxPerSec;
    const marker = document.createElement('div');
    marker.className = 'ruler-error-marker';
    marker.style.left = `${leftPx}px`;
    marker.title = `${err.title} (${timeSec.toFixed(2)}s)`;
    
    marker.onclick = (e) => {
      e.stopPropagation();
      updatePlayheadPosition(err.start_us);
      switchAssetTab('scanner', document.getElementById('tabScannerBtn'));
      flashBoundingBox(err.id);
    };
    
    lane.appendChild(marker);
  });
}

// 17. Execute Single Error Auto-Fix
async function executeSingleAutoFix(errorId) {
  const err = detectedErrors.find(e => e.id === errorId);
  const title = err ? err.title : errorId;
  
  logAgentTerminal(`[AI-ACTION] Đang thực thi sửa vùng lỗi: "${title}"...`, 't-exec');
  showLiveAgentHud(title);
  
  try {
    const res = await fetch('/api/ai-agent/auto-fix-step', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_name: currentProject,
        error_id: errorId
      })
    });
    
    const data = await res.json();
    if (data.status === 'success') {
      agentFixedIds.add(errorId);
      if (err) err.fixed = true;
      
      logAgentTerminal(`[AI-SUCCESS] ${data.action_performed}`, 't-success');
      
      // Morph bounding box to green check
      const boxEl = document.getElementById(`bbox_${errorId}`);
      if (boxEl) {
        boxEl.classList.add('is-fixed');
        boxEl.innerHTML = `
          <div class="bbox-corner tl"></div>
          <div class="bbox-corner tr"></div>
          <div class="bbox-corner bl"></div>
          <div class="bbox-corner br"></div>
          <div class="bbox-header-badge" style="border-color:#10b981;color:#10b981;">
            <span>✓ ĐÃ SỬA HOÀN TẤT</span>
          </div>
        `;
      }
      
      setTimeout(async () => {
        hideLiveAgentHud();
        await loadProject(currentProject);
      }, 400);
    }
  } catch (err) {
    logAgentTerminal(`[AI-ERROR] Không thể sửa lỗi: ${err.message}`, 't-crit');
    hideLiveAgentHud();
  }
}

// 18. AI AGENT REALTIME AUTONOMOUS DIRECTOR ENGINE
function toggleLiveAgentModal() {
  const modal = document.getElementById('liveAgentModal');
  if (modal.classList.contains('open')) {
    closeLiveAgentModal();
  } else {
    modal.classList.add('open');
    trapModalFocus(modal);
    scanCurrentProjectErrors();
  }
}

function closeLiveAgentModal() {
  document.getElementById('liveAgentModal').classList.remove('open');
  pauseAgent();
  releaseModalFocus();
}

function startLiveAIAgentEdit() {
  toggleLiveAgentModal();
  setTimeout(() => {
    runAgentAutoPilot();
  }, 250);
}

function updateCockpitMetrics(scanData) {
  const totalEl = document.getElementById('cockpitTotalErrors');
  if (totalEl) totalEl.textContent = scanData.total_errors || 0;
  
  const fixedEl = document.getElementById('cockpitFixedCount');
  if (fixedEl) fixedEl.textContent = agentFixedIds.size;
  
  const scoreEl = document.getElementById('cockpitHealthScore');
  if (scoreEl) scoreEl.textContent = `${scanData.health_score || 85}%`;
  
  const modeTag = document.getElementById('agentModeTag');
  if (modeTag) {
    if (isAgentAutoRunning) {
      modeTag.textContent = 'ĐANG BIÊN TẬP REALTIME';
      modeTag.style.background = '#0284c7';
    } else if (scanData.total_errors === 0) {
      modeTag.textContent = 'HOÀN HẢO 100%';
      modeTag.style.background = '#10b981';
    } else {
      modeTag.textContent = 'SẴN SÀNG';
      modeTag.style.background = '#334155';
    }
  }
}

function logAgentTerminal(msg, typeClass = 't-system') {
  const body = document.getElementById('agentTerminalBody');
  if (!body) return;
  
  const now = new Date();
  const timeStr = now.toTimeString().split(' ')[0] + '.' + String(now.getMilliseconds()).padStart(3, '0');
  
  const line = document.createElement('div');
  line.className = `t-line ${typeClass}`;
  line.textContent = `[${timeStr}] ${msg}`;
  body.appendChild(line);
  body.scrollTop = body.scrollHeight;
}

function showLiveAgentHud(actionText) {
  const hud = document.getElementById('liveAgentHudBanner');
  const textEl = document.getElementById('hudSubAction');
  if (hud && textEl) {
    textEl.textContent = actionText;
    hud.style.display = 'flex';
  }
}

function hideLiveAgentHud() {
  const hud = document.getElementById('liveAgentHudBanner');
  if (hud) hud.style.display = 'none';
}

async function runAgentAutoPilot() {
  if (isAgentAutoRunning) return;
  isAgentAutoRunning = true;
  
  const btn = document.getElementById('btnRunAgentAuto');
  if (btn) {
    btn.innerHTML = '<span class="btn-icon">⏸</span> Đang Chạy Tự Động...';
    btn.style.background = '#059669';
  }
  
  logAgentTerminal('=== BẮT ĐẦU QUY TRÌNH AI AGENT EDIT VIDEO REALTIME ===', 't-seek');
  
  const executeNextLoop = async () => {
    if (!isAgentAutoRunning) return;
    
    // Find next unfixed error
    const nextErr = detectedErrors.find(e => !agentFixedIds.has(e.id) && !e.fixed);
    
    if (!nextErr) {
      logAgentTerminal('🎉 TOÀN BỘ VÙNG LỖI ĐÃ ĐƯỢC AI AGENT TỰ ĐỘNG KHẮC PHỤC TRIỆT ĐỂ!', 't-success');
      logAgentTerminal('✓ Quality Gate Score: 100/100 (Pass Commercial Standard).', 't-success');
      
      const spotlightTitle = document.getElementById('spotlightTitle');
      if (spotlightTitle) spotlightTitle.textContent = '✓ AI Agent đã hoàn tất biên tập video!';
      const spotlightBadge = document.getElementById('spotlightBadge');
      if (spotlightBadge) spotlightBadge.textContent = 'HOÀN THÀNH XUẤT SẮC';
      
      pauseAgent();
      hideLiveAgentHud();
      await loadProject(currentProject);
      return;
    }
    
    // Step 1: Seek playhead to error location
    const targetTimeUs = nextErr.target_time_us || nextErr.start_us;
    updatePlayheadPosition(targetTimeUs);
    
    // Step 2: Spotlight HUD & Terminal
    const spotlightBadge = document.getElementById('spotlightBadge');
    if (spotlightBadge) spotlightBadge.textContent = `BƯỚC XỬ LÝ [${nextErr.category.toUpperCase()}]`;
    
    const spotlightTitle = document.getElementById('spotlightTitle');
    if (spotlightTitle) spotlightTitle.textContent = nextErr.title;
    
    const spotlightDesc = document.getElementById('spotlightDesc');
    if (spotlightDesc) spotlightDesc.textContent = `AI Agent đang khoanh vùng và áp dụng: "${nextErr.fix_command}"`;
    
    logAgentTerminal(`[AI-SEEK] Di chuyển Playhead đến ${(targetTimeUs/1e6).toFixed(2)}s`, 't-seek');
    logAgentTerminal(`[AI-BBOX] Khoanh vùng phát hiện lỗi: ${nextErr.title}`, 't-bbox');
    
    showLiveAgentHud(nextErr.title);
    flashBoundingBox(nextErr.id);
    
    // Step 3: Wait 550ms so user can watch the bounding box being targeted
    agentAutoTimer = setTimeout(async () => {
      if (!isAgentAutoRunning) return;
      
      await executeSingleAutoFix(nextErr.id);
      
      // Step 4: Wait 450ms then schedule next repair
      agentAutoTimer = setTimeout(() => {
        executeNextLoop();
      }, 500);
    }, 600);
  };
  
  executeNextLoop();
}

async function runAgentNextStep() {
  const nextErr = detectedErrors.find(e => !agentFixedIds.has(e.id) && !e.fixed);
  if (!nextErr) {
    showToast('Tất cả các vùng lỗi trên timeline đã được xử lý xong!', 'success');
    return;
  }
  
  updatePlayheadPosition(nextErr.target_time_us || nextErr.start_us);
  flashBoundingBox(nextErr.id);
  await executeSingleAutoFix(nextErr.id);
}

async function executeBatchAutoFix() {
  logAgentTerminal('[AI-BATCH] Đang kích hoạt chế độ sửa siêu tốc toàn bộ...', 't-exec');
  showLiveAgentHud('AI Agent đang tối ưu toàn bộ timeline...');
  
  try {
    const res = await fetch('/api/ai-agent/auto-fix-all', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_name: currentProject })
    });
    
    const data = await res.json();
    if (data.status === 'success') {
      (data.actions_log || []).forEach(logItem => {
        logAgentTerminal(logItem, 't-success');
      });
      
      logAgentTerminal('✓ Đã đồng bộ toàn bộ thay đổi vào file draft_content.json CapCut!', 't-success');
      agentFixedIds.clear();
      
      setTimeout(async () => {
        hideLiveAgentHud();
        await loadProject(currentProject);
      }, 500);
    }
  } catch (err) {
    logAgentTerminal(`[AI-ERROR] Lỗi batch fix: ${err.message}`, 't-crit');
    hideLiveAgentHud();
  }
}

function pauseAgent() {
  isAgentAutoRunning = false;
  if (agentAutoTimer) clearTimeout(agentAutoTimer);
  agentAutoTimer = null;
  
  const btn = document.getElementById('btnRunAgentAuto');
  if (btn) {
    btn.innerHTML = '<span class="btn-icon">▶</span> Chạy Tự Động (Auto-Pilot)';
    btn.style.background = '';
  }
  
  const modeTag = document.getElementById('agentModeTag');
  if (modeTag) {
    modeTag.textContent = 'TẠM DỪNG';
    modeTag.style.background = '#64748b';
  }
  
  hideLiveAgentHud();
  logAgentTerminal('[AGENT] Đã tạm dừng quy trình tự động.', 't-system');
}

/* ==========================================================================
   19. MCP STUDIO & TIMELINE BUILDER HANDLERS
   ========================================================================== */

const MCP_PRESETS = {
  cup: [
    { text: "CHỈ TỪ 1.100Đ MỘT CHIẾC LY GIẤY CAO CẤP", type: "vj", startSec: 0, endSec: 2.5, durationSec: 2.5, keyword: "ly_giay" },
    { text: "IN ẤN SẮC NÉT KHÔNG LEM MỰC CHUẨN THƯƠNG HIỆU", type: "broll", startSec: 2.5, endSec: 5.2, durationSec: 2.7, keyword: "in_an" },
    { text: "TRÁNG MÀNG PE KÉP CHỐNG THẤM NƯỚC TUYỆT ĐỐI", type: "broll", startSec: 5.2, endSec: 7.8, durationSec: 2.6, keyword: "chong_tham" },
    { text: "GIAO HÀNG TOÀN QUỐC HỖ TRỢ THIẾT KẾ MIỄN PHÍ", type: "vj", startSec: 7.8, endSec: 10.5, durationSec: 2.7, keyword: "giao_hang" }
  ],
  coffee: [
    { text: "HƯƠNG VỊ CÀ PHÊ NGUYÊN BẢN ĐẬM ĐÀ", type: "vj", startSec: 0, endSec: 2.8, durationSec: 2.8, keyword: "ca_phe" },
    { text: "HẠT ROBUSTA ĐẮK LẮK RANG MỘC THỦ CÔNG", type: "broll", startSec: 2.8, endSec: 5.6, durationSec: 2.8, keyword: "rang_moc" },
    { text: "TRẢI NGHIỆM NGAY HÔM NAY ĐỂ NHẬN ƯU ĐÃI", type: "vj", startSec: 5.6, endSec: 8.5, durationSec: 2.9, keyword: "uu_dai" }
  ]
};

let mcpDiagnosticResults = null;
let mcpExcludedClips = new Set();

function openMcpModal() {
  const modal = document.getElementById('mcpModal');
  if (modal) {
    modal.classList.add('active');
    modal.classList.add('open');
    trapModalFocus(modal);
    
    // Tự động điền đường dẫn từ project hiện tại nếu có
    const projInput = document.getElementById('mcpProjectName');
    const brollInput = document.getElementById('mcpBrollFolder');
    const supInput = document.getElementById('mcpSupportingFolder');
    
    if (projInput && !projInput.value) {
      projInput.value = currentProject || (projectData && projectData.project_name) || '';
    }
    if (projectData && projectData.path) {
      const projDir = String(projectData.path).replace(/[\\\/]draft_content\.json$/i, '').replace(/\\/g, '/');
      if (brollInput && !brollInput.value && projDir) {
        brollInput.value = `${projDir}/materials/video`;
      }
      if (supInput && !supInput.value && projDir) {
        supInput.value = `${projDir}/materials`;
      }
    }

    if (!document.getElementById('mcpScriptJson').value) {
      loadMcpPreset('cup');
    }
  }
}

function closeMcpModal(event) {
  if (event && event.target && event.target.id !== 'mcpModal' && !event.target.classList.contains('btn-close-modal')) {
    return;
  }
  const modal = document.getElementById('mcpModal');
  if (modal) {
    modal.classList.remove('active');
    modal.classList.remove('open');
    releaseModalFocus();
  }
}

function switchMcpTab(tabName, btnEl) {
  document.querySelectorAll('.mcp-tab-btn').forEach(btn => btn.classList.remove('active'));
  if (btnEl) btnEl.classList.add('active');
  
  document.querySelectorAll('.mcp-pane').forEach(p => p.classList.remove('active'));
  const targetPane = document.getElementById(`mcpPane-${tabName}`);
  if (targetPane) targetPane.classList.add('active');
}

function loadMcpPreset(type) {
  document.querySelectorAll('.mcp-preset-pill').forEach(btn => btn.classList.remove('active'));
  const activeBtn = event?.currentTarget || document.querySelector(`.mcp-preset-pill[onclick*="${type}"]`);
  if (activeBtn) activeBtn.classList.add('active');
  
  const rawTextarea = document.getElementById('mcpRawScriptText');
  const projInput = document.getElementById('mcpProjectName');
  const hookInput = document.getElementById('mcpDirectorHook');
  const ctaInput = document.getElementById('mcpDirectorCta');
  
  if (type === 'cup') {
    if (projInput && !projInput.value) projInput.value = currentProject || 'DU_AN_LY_GIAY';
    if (hookInput) hookInput.value = 'CẢNH BÁO: ĐỪNG DÙNG LY NHỰA NỮA!';
    if (ctaInput) ctaInput.value = 'BẤM VÀO GIỎ HÀNG NHẬN CHIẾT KHẤU 20%';
    if (rawTextarea) {
      rawTextarea.value = `1. Ly giấy sinh học thế hệ mới, giải pháp xanh thay thế hoàn toàn nhựa dùng một lần. (broll: ly_giay)
2. Chống thấm nước tuyệt đối, an toàn cho cả đồ uống nóng và lạnh suốt 12 tiếng. (broll: chong_tham)
3. Thiết kế in ấn logo sắc nét theo yêu cầu, nâng tầm nhận diện thương hiệu quán của bạn. (broll: may_in)
4. Nhấp vào giỏ hàng ngay hôm nay để nhận ưu đãi chiết khấu 20% cho 50 đơn đầu tiên! (broll: uu_dai)`;
    }
  } else if (type === 'coffee') {
    if (projInput && !projInput.value) projInput.value = currentProject || 'DU_AN_CA_PHE';
    if (hookInput) hookInput.value = 'BÍ QUYẾT ĐẬM ĐÀ CỦA CÀ PHÊ MỘC!';
    if (ctaInput) ctaInput.value = 'MUA NGAY HÔM NAY TẶNG KÈM PHIN NHÔM';
    if (rawTextarea) {
      rawTextarea.value = `1. Hương vị đậm đà nguyên bản từ những hạt cà phê Robusta tuyển chọn chín mọng 100%. (broll: hat_caphe)
2. Công nghệ rang mộc mẻ nhỏ thủ công, giữ trọn vẹn từng tầng hương thơm và lớp crema béo ngậy. (broll: rang_moc)
3. Thưởng thức một ly cà phê chuẩn vị mỗi sớm mai, bừng tỉnh năng lượng và khởi đầu ngày mới tuyệt vời! (broll: thuong_thuc)`;
    }
  } else if (type === 'retail') {
    if (projInput && !projInput.value) projInput.value = currentProject || 'DU_AN_SIEU_SALE';
    if (hookInput) hookInput.value = 'SIÊU SALE DUY NHẤT 24 GIỜ!';
    if (ctaInput) ctaInput.value = 'NHANH TAY CHỐT ĐƠN KẺO HẾT VOUCHER';
    if (rawTextarea) {
      rawTextarea.value = `1. Cơ hội sở hữu trọn bộ sản phẩm cao cấp với mức giá ưu đãi chưa từng có. (broll: san_pham)
2. Cam kết chính hãng 100%, bảo hành 1 đổi 1 trong 30 ngày và giao hỏa tốc tận nhà. (broll: bao_hanh)
3. Nhanh tay nhấp vào liên kết bên dưới để gom voucher giảm 50% trước khi hết số lượng! (broll: voucher)`;
    }
  }
  
  triggerParseScriptAI();
  logMcpTerminal(`[MCP-PRESET] Đã nạp mẫu kịch bản "${type.toUpperCase()}"`);
}

function onPacingModeChange() {
  triggerParseScriptAI();
}

async function triggerParseScriptAI() {
  const rawScript = document.getElementById('mcpRawScriptText')?.value.trim();
  const pacingMode = document.getElementById('mcpDirectorPacing')?.value || 'medium';
  if (!rawScript) return;
  
  logMcpTerminal(`[AI-SCRIPT] Đang phân tích kịch bản theo nhịp dựng "${pacingMode.toUpperCase()}"...`);
  try {
    const res = await fetch('/api/ai-agent/parse-script', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        raw_script: rawScript,
        pacing_mode: pacingMode
      })
    });
    const data = await res.json();
    if (data.ok) {
      const codeArea = document.getElementById('mcpScriptJson');
      if (codeArea) {
        codeArea.value = JSON.stringify(data.sentences, null, 2);
      }
      logMcpTerminal(`[AI-SCRIPT] ✓ Đã bóc tách ${data.count} phân cảnh (căn nhịp timecode, phân loại VJ/B-Roll và từ khóa footage thành công).`);
    } else {
      logMcpTerminal(`[AI-SCRIPT] Lỗi: ${data.detail || 'Không thể bóc tách'}`);
    }
  } catch (err) {
    logMcpTerminal(`[AI-SCRIPT] Lỗi kết nối: ${err.message}`);
  }
}

async function runFootageAnalysisFromInput() {
  const folderPath = document.getElementById('mcpBrollFolder')?.value.trim();
  if (!folderPath) {
    showToast('Vui lòng nhập đường dẫn thư mục Footage', 'warn');
    return;
  }
  
  logMcpTerminal(`[AI-FOOTAGE] Khởi động AI Agent & OpenCV quét chẩn đoán folder: "${folderPath}"...`);
  
  // Switch to Diagnostic Tab
  const diagTabBtn = document.getElementById('mcpTabDiagnosticBtn');
  switchMcpTab('diagnostic', diagTabBtn);
  
  const container = document.getElementById('mcpFootageCardsGrid');
  if (container) {
    container.innerHTML = '<div class="mcp-empty-diag"><span class="scanner-spinner"></span> AI Agent đang đo tỷ lệ cháy sáng (overexposed), rung lắc camera và mất nét...</div>';
  }
  
  try {
    const res = await fetch('/api/ai-agent/analyze-footage-folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        folder_path: folderPath,
        max_files: 25
      })
    });
    
    const data = await res.json();
    if (data.status === 'success') {
      mcpDiagnosticResults = data;
      renderDiagnosticResults(data);
    } else {
      logMcpTerminal(`[AI-FOOTAGE] Lỗi phân tích: ${data.message || 'Không quét được folder'}`);
      if (container) container.innerHTML = `<div class="mcp-empty-diag" style="color:#ef4444;">${esc(data.message || 'Lỗi quét folder')}</div>`;
    }
  } catch (err) {
    logMcpTerminal(`[AI-FOOTAGE] Lỗi kết nối: ${err.message}`);
    if (container) container.innerHTML = `<div class="mcp-empty-diag" style="color:#ef4444;">Lỗi kết nối: ${esc(err.message)}</div>`;
  }
}

function renderDiagnosticResults(data) {
  const { summary, proposals, files } = data;
  
  // 1. Update Counters
  document.getElementById('diagTotalScanned').textContent = summary.total_scanned || 0;
  document.getElementById('diagTotalApproved').textContent = summary.approved_count || 0;
  document.getElementById('diagTotalWarning').textContent = summary.warning_count || 0;
  document.getElementById('diagTotalRejected').textContent = summary.rejected_count || 0;
  
  const badBadge = document.getElementById('mcpBadgeBadClips');
  if (badBadge) {
    const badTotal = (summary.rejected_count || 0);
    badBadge.textContent = badTotal;
    badBadge.classList.toggle('active', badTotal > 0);
  }
  
  // 2. Proposal Box
  const propBody = document.getElementById('mcpAiProposalText');
  if (propBody && proposals && proposals.length > 0) {
    propBody.innerHTML = proposals.map(p => `<div>• ${esc(p)}</div>`).join('');
  }
  
  // 3. Render Cards
  const container = document.getElementById('mcpFootageCardsGrid');
  if (!container) return;
  container.innerHTML = '';
  
  mcpExcludedClips.clear();
  
  files.forEach(f => {
    const card = document.createElement('div');
    const statusClass = (f.status || 'acceptable').toLowerCase();
    card.className = `mcp-footage-card card-${statusClass}`;
    
    // Auto-exclude rejected clips
    const isApproved = f.approved;
    if (!isApproved) {
      mcpExcludedClips.add(f.file_path);
    }
    
    // Fill color helpers
    const expClass = f.overexposed_pct > 22 ? 'fill-bad' : (f.overexposed_pct > 10 ? 'fill-warn' : 'fill-ok');
    const shakeClass = f.shake_score > 24 ? 'fill-bad' : (f.shake_score > 15 ? 'fill-warn' : 'fill-ok');
    
    const badgeMap = {
      'EXCELLENT': '<span class="diag-badge badge-pass">✓ ĐẠT CHUẨN</span>',
      'ACCEPTABLE': '<span class="diag-badge badge-pass">✓ CHẤP NHẬN</span>',
      'WARNING': '<span class="diag-badge badge-warn">⚠️ CẢNH BÁO</span>',
      'REJECTED': '<span class="diag-badge badge-fail">✕ LOẠI BỎ</span>'
    };
    
    card.innerHTML = `
      <div class="card-left">
        <div class="card-icon">${f.status === 'REJECTED' ? '🚫' : (f.status === 'WARNING' ? '⚠️' : '🎬')}</div>
        <div class="card-name-col">
          <div class="card-fname" title="${esc(f.file_name)}">${esc(f.file_name)}</div>
          <div class="card-meta">${Number(f.duration_sec) || 0}s · ${esc(f.resolution)} · ${esc(f.diagnosis)}</div>
        </div>
      </div>

      <div class="card-metrics">
        <div class="metric-col" title="Tỷ lệ pixel trắng cháy sáng (ngưỡng 22%)">
          <div class="metric-header">
            <span>Cháy Sáng:</span>
            <span>${Number(f.overexposed_pct) || 0}%</span>
          </div>
          <div class="metric-bar-bg">
            <div class="metric-bar-fill ${expClass}" style="width: ${Math.min(100, (Number(f.overexposed_pct) || 0) * 3)}%"></div>
          </div>
        </div>

        <div class="metric-col" title="Độ dao động camera rung lắc (ngưỡng 24.0)">
          <div class="metric-header">
            <span>Rung Lắc:</span>
            <span>${Number(f.shake_score) || 0}</span>
          </div>
          <div class="metric-bar-bg">
            <div class="metric-bar-fill ${shakeClass}" style="width: ${Math.min(100, (Number(f.shake_score) || 0) * 3)}%"></div>
          </div>
        </div>
      </div>

      <div class="card-actions">
        ${badgeMap[f.status] || badgeMap.ACCEPTABLE}
        <label class="mcp-check-item" title="Đánh dấu để cho phép bốc vào timeline hoặc loại trừ">
          <input type="checkbox" class="footage-approval-chk" ${isApproved ? 'checked' : ''}>
          <span>Duyệt</span>
        </label>
      </div>
    `;

    const chk = card.querySelector('.footage-approval-chk');
    if (chk) {
      chk.addEventListener('change', (e) => {
        toggleFootageApproval(f.file_path.replace(/\\/g, '/'), e.target.checked);
      });
    }
    
    container.appendChild(card);
  });
  
  logMcpTerminal(`[AI-FOOTAGE] ✓ Hoàn tất phân tích ${files.length} clip. Phát hiện ${summary.rejected_count} clip lỗi đã tự động loại bỏ.`);
}

function toggleFootageApproval(filePath, isChecked) {
  if (isChecked) {
    mcpExcludedClips.delete(filePath);
    logMcpTerminal(`[AI-SELECT] Đã duyệt đưa lại clip vào pool: ${filePath.split('/').pop()}`);
  } else {
    mcpExcludedClips.add(filePath);
    logMcpTerminal(`[AI-SELECT] Đã loại trừ clip khỏi pool B-Roll: ${filePath.split('/').pop()}`);
  }
}

function logMcpTerminal(msg) {
  const body = document.getElementById('mcpTermBody');
  if (!body) return;
  const now = new Date();
  const timeStr = now.toTimeString().split(' ')[0];
  const line = document.createElement('div');
  line.className = 'mcp-log-line';
  line.textContent = `[${timeStr}] ${msg}`;
  body.appendChild(line);
  body.scrollTop = body.scrollHeight;
}

async function triggerMcpCompile() {
  const projName = document.getElementById('mcpProjectName')?.value.trim();
  const brollFolder = document.getElementById('mcpBrollFolder')?.value.trim();
  const supportingFolder = document.getElementById('mcpSupportingFolder')?.value.trim();
  const vjVideo = document.getElementById('mcpVjVideo')?.value.trim();
  const bgmPath = document.getElementById('mcpBgmPath')?.value.trim();
  const hookText = document.getElementById('mcpDirectorHook')?.value.trim();
  const ctaText = document.getElementById('mcpDirectorCta')?.value.trim();
  const scriptRaw = document.getElementById('mcpScriptJson')?.value.trim();
  
  if (!projName) {
    showToast('Vui lòng nhập tên dự án', 'warn');
    return;
  }
  
  let scriptSentences = [];
  try {
    scriptSentences = JSON.parse(scriptRaw);
  } catch (err) {
    showToast('Kịch bản JSON không đúng định dạng. Hãy nhấn nút "AI Agent Phân Tích & Căn Nhịp" trước.', 'error');
    return;
  }
  
  const btn = document.getElementById('btnCompileMcp');
  btn.disabled = true;
  btn.innerHTML = '<span class="scanner-spinner"></span> Đang biên dịch 13 Layers...';
  
  const excludedArr = Array.from(mcpExcludedClips);
  
  logMcpTerminal(`[MCP-START] Khởi chạy tiến trình biên dịch CapCut 13 Layers cho "${projName}"...`);
  if (excludedArr.length > 0) {
    logMcpTerminal(`[MCP-FILTER] Đã lọc bỏ ${excludedArr.length} clip cháy sáng / rung lắc khỏi bể B-Roll.`);
  }
  
  try {
    const res = await fetch('/api/mcp/create-project', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        projectName: projName,
        vjVideoPath: vjVideo,
        brollFolderPath: brollFolder,
        supportingFolder: supportingFolder,
        bgmPath: bgmPath,
        hookText: hookText,
        ctaText: ctaText,
        excludedClipPaths: excludedArr,
        scriptSentences: scriptSentences
      })
    });
    
    const result = await res.json();
    if (result.ok) {
      logMcpTerminal(`[MCP-SUCCESS] ✓ Dự án "${result.projectName}" đã được tạo thành công!`);
      logMcpTerminal(`[MCP-SYNC] Đã phân tầng 13 Layers: VJ Track 0, B-roll chống trùng Track 1, Mic Boost (+10dB) Track 8, BGM Ducking Track 9, Montserrat Safe Zone Track 10.`);
      logMcpTerminal(`[MCP-LOAD] Đang nạp ngay dự án vào Web Studio...`);
      
      await fetchProjects();
      currentProject = result.projectName;
      const select = document.getElementById('projectSelect');
      if (select) select.value = result.projectName;
      
      await loadProject(result.projectName);
      
      setTimeout(() => {
        closeMcpModal();
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">🚀</span> BIÊN DỊCH DỰ ÁN 13 LỚP QUA MCP';
      }, 900);
    } else {
      logMcpTerminal(`[MCP-ERR] Thất bại: ${result.error}`);
      btn.disabled = false;
      btn.innerHTML = '<span class="btn-icon">🚀</span> BIÊN DỊCH DỰ ÁN 13 LỚP QUA MCP';
    }
  } catch (err) {
    logMcpTerminal(`[MCP-ERR] Lỗi kết nối: ${err.message}`);
    btn.disabled = false;
    btn.innerHTML = '<span class="btn-icon">🚀</span> BIÊN DỊCH DỰ ÁN 13 LỚP QUA MCP';
  }
}



