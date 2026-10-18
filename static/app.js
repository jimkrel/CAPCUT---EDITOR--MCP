// ==========================================================================
// CAPCUT AI PRODUCER & CO-DIRECTOR PRO — SLEEK CLIENT RUNTIME
// ==========================================================================

let projectsCache = [];
let activeTab = 'create';

// Escape HTML chống XSS
function esc(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// Hệ thống Toast Notification
function showToast(message, type = 'info', duration = 3500) {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  while (container.children.length >= 3) {
    container.firstElementChild.remove();
  }

  const toast = document.createElement('div');
  toast.className = `toast-item toast-${type}`;

  const icon = type === 'success' ? '✓' : (type === 'error' ? '✕' : (type === 'warn' ? '⚠' : 'ℹ'));
  toast.innerHTML = `
    <span class="toast-icon">${icon}</span>
    <span class="toast-msg">${esc(message)}</span>
    <button class="toast-close-btn" type="button" aria-label="Đóng">&times;</button>
  `;

  toast.querySelector('.toast-close-btn').onclick = () => toast.remove();
  container.appendChild(toast);

  setTimeout(() => {
    if (toast.parentNode) toast.remove();
  }, duration);
}

// Chuyển Tab: 'create' hoặc 'projects'
function switchTab(tab) {
  activeTab = tab;
  const tabBtnCreate = document.getElementById('tabBtnCreate');
  const tabBtnProjects = document.getElementById('tabBtnProjects');
  const paneCreate = document.getElementById('paneCreate');
  const paneProjects = document.getElementById('paneProjects');

  if (tab === 'projects') {
    tabBtnCreate?.classList.remove('active');
    tabBtnProjects?.classList.add('active');
    paneCreate?.classList.remove('active');
    paneProjects?.classList.add('active');
    loadProjects(true);
  } else {
    tabBtnProjects?.classList.remove('active');
    tabBtnCreate?.classList.add('active');
    paneProjects?.classList.remove('active');
    paneCreate?.classList.add('active');
  }
}

// Tải danh sách dự án CapCut từ server
async function loadProjects(forceRefresh = false) {
  const countLabel = document.getElementById('labelProjectsCount');
  const statusPill = document.getElementById('capcutStatusPill');
  const statusText = document.getElementById('capcutStatusText');

  try {
    const res = await fetch('/api/projects');
    if (!res.ok) throw new Error('Không thể tải danh sách dự án');
    const data = await res.json();
    projectsCache = data.projects || [];

    if (countLabel) countLabel.textContent = `(${projectsCache.length} dự án)`;

    if (statusPill && statusText) {
      if (data.capcut_running) {
        statusPill.classList.add('running');
        statusText.textContent = 'CapCut Desktop: Đang chạy';
      } else {
        statusPill.classList.remove('running');
        statusText.textContent = 'CapCut Desktop: Sẵn sàng';
      }
    }

    renderProjects(projectsCache);
  } catch (err) {
    if (countLabel) countLabel.textContent = `(Lỗi tải)`;
    console.error('Lỗi tải dự án:', err);
    const grid = document.getElementById('gridProjectsContainer');
    if (grid) {
      grid.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 30px; text-align: center; color: #f43f5e; background: rgba(244,63,94,0.1); border-radius: 10px;">
          <div>⚠️ Không thể kết nối đến máy chủ: ${esc(err.message)}</div>
          <button class="hub-btn-action" style="margin: 12px auto 0;" onclick="loadProjects(true)">🔄 Thử lại</button>
        </div>
      `;
    }
  }
}

// Render grid các Card dự án
function renderProjects(projects) {
  const grid = document.getElementById('gridProjectsContainer');
  if (!grid) return;

  if (!projects || projects.length === 0) {
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; padding: 48px 24px; text-align: center; color: #64748b; background: #131722; border-radius: 12px; border: 1px dashed rgba(255,255,255,0.1);">
        <div style="font-size: 36px; margin-bottom: 10px;">📂</div>
        <div style="font-size: 15px; font-weight: 700; color: #f1f5f9;">Chưa có dự án nào trong CapCut</div>
        <div style="font-size: 12.5px; color: #94a3b8; margin: 6px 0 16px;">Bạn có thể nhập thư mục dự án từ máy tính hoặc bấm "Tạo Dự Án Mới" để AI tự động dựng 13 lớp!</div>
        <button class="hub-btn-primary" style="margin: 0 auto;" onclick="switchTab('create')">
          <span>✨</span> Tạo Dự Án Mới Ngay
        </button>
      </div>
    `;
    return;
  }

  grid.innerHTML = projects.map(p => {
    const dateStr = p.modified ? new Date(p.modified * 1000).toLocaleString('vi-VN') : 'Không rõ';
    const dur = p.duration_sec ? `${p.duration_sec}s` : '0s';
    const clips = p.video_count !== undefined ? `${p.video_count} clip` : '0 clip';
    const texts = p.text_count !== undefined ? `${p.text_count} sub` : '0 sub';
    const safeName = esc(p.name);

    return `
      <div class="hub-project-card">
        <div class="card-head">
          <div class="card-icon">🎬</div>
          <div class="card-meta">
            <div class="card-title" title="${safeName}">${safeName}</div>
            <div class="card-date">🕒 Cập nhật: ${dateStr}</div>
          </div>
        </div>
        <div class="card-stats">
          <div class="stat-badge">⏱️ ${dur}</div>
          <div class="stat-badge">🎞️ ${clips}</div>
          <div class="stat-badge">💬 ${texts}</div>
        </div>
        <div class="card-actions">
          <button class="btn-card-launch" type="button" onclick="openProjectInCapcut('${safeName}', this)" title="Kích hoạt nạp thẳng vào CapCut Desktop">
            <span>🎬</span> Mở CapCut Desktop
          </button>
          <button class="btn-card-scan" type="button" onclick="scanProjectFootage('${safeName}')" title="Quét lọc lỗi footage dự án này">
            <span>🔍</span> Quét Lỗi
          </button>
        </div>
      </div>
    `;
  }).join('');
}

// Tìm kiếm lọc dự án theo tên
function filterProjects(query) {
  const q = (query || '').toLowerCase().trim();
  if (!q) {
    renderProjects(projectsCache);
    return;
  }
  const filtered = projectsCache.filter(p => (p.name || '').toLowerCase().includes(q));
  renderProjects(filtered);
}

// Mở dự án trực tiếp vào CapCut Desktop
async function openProjectInCapcut(projectName, btn) {
  const origHtml = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="scanner-spinner"></span> Đang mở...';
  }

  try {
    const res = await fetch('/api/capcut/open-project', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projectName })
    });
    const data = await res.json();
    if (data.ok) {
      showToast(`✓ Đã nạp và kích hoạt dự án "${projectName}" trên CapCut Desktop!`, 'success');
      loadProjects();
    } else {
      showToast(data.message || data.error || 'Đã nạp dự án vào CapCut.', 'info');
    }
  } catch (err) {
    showToast(`Lỗi mở CapCut: ${err.message}`, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = origHtml;
    }
  }
}

// Kích hoạt app CapCut Desktop từ Header
async function launchCapcutApp() {
  const firstProj = projectsCache.length > 0 ? projectsCache[0].name : '';
  try {
    const res = await fetch('/api/capcut/open-project', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projectName: firstProj })
    });
    const data = await res.json();
    showToast(data.message || 'CapCut Desktop đã được kích hoạt!', 'success');
    loadProjects();
  } catch (err) {
    showToast(`Lỗi kích hoạt CapCut: ${err.message}`, 'error');
  }
}

// Nhập dự án từ folder bất kỳ trên máy
async function importCustomProject() {
  const pathInput = document.getElementById('inputCustomDraftPath');
  const rawPath = pathInput ? pathInput.value.trim() : '';
  if (!rawPath) {
    showToast('Vui lòng dán đường dẫn thư mục dự án CapCut', 'warn');
    return;
  }

  try {
    const res = await fetch('/api/projects/import-folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folderPath: rawPath })
    });
    const data = await res.json();
    if (data.ok) {
      showToast(data.message || `Đã nhập dự án "${data.projectName}" thành công!`, 'success');
      pathInput.value = '';
      await loadProjects(true);
    } else {
      showToast(data.detail || data.error || 'Không thể nhập dự án', 'error');
    }
  } catch (err) {
    showToast(`Lỗi kết nối: ${err.message}`, 'error');
  }
}

// Tạo tên dự án ngẫu nhiên theo thời gian
function generateRandomProjectName() {
  const now = new Date();
  const pad = n => String(n).padStart(2, '0');
  const name = `COMMERCIAL_${now.getFullYear()}${pad(now.getMonth()+1)}${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}`;
  const input = document.getElementById('inputProjectName');
  if (input) input.value = name;
  return name;
}

// Phân tích kịch bản đạo diễn Plain Text
function parseDirectorRequirements(raw) {
  let hook = '';
  let cta = '';
  let pacing = '2.5s';
  if (!raw || !raw.trim()) return { hook, cta, pacing };

  const lines = raw.split('\n').map(l => l.trim()).filter(Boolean);
  for (const line of lines) {
    const mHook = line.match(/^(?:Hook|Tiêu đề|Mở đầu|Banner|Hook 3s)[\s:：\-]+(.*)$/i);
    if (mHook) { hook = mHook[1].trim(); continue; }

    const mCta = line.match(/^(?:CTA|Kêu gọi|Hành động|Outro|Kết)[\s:：\-]+(.*)$/i);
    if (mCta) { cta = mCta[1].trim(); continue; }

    const mPacing = line.match(/^(?:Pacing|Nhịp|Tốc độ|Nhịp cắt)[\s:：\-]+(.*)$/i);
    if (mPacing) { pacing = mPacing[1].trim(); continue; }

    const mSec = line.match(/(?:nhịp\s*)?(\d+(?:\.\d+)?\s*s)/i);
    if (mSec && !mHook && !mCta) { pacing = mSec[1].trim(); continue; }
  }

  if (!hook && lines.length > 0) {
    hook = lines[0].replace(/^(?:Hook|Tiêu đề)[\s:：\-]+/i, '');
  }
  if (!cta && lines.length > 1) {
    cta = lines[lines.length - 1].replace(/^(?:CTA|Kêu gọi)[\s:：\-]+/i, '');
  }

  return { hook, cta, pacing };
}

// Mẫu nhanh cho Kịch bản
function fillSampleScript(type) {
  const txt = document.getElementById('inputRawScript');
  const dirEl = document.getElementById('inputDirectorPrompt');
  if (!txt) return;

  if (type === 'fb') {
    txt.value = `Bạn có biết tại sao trà sữa ở đây luôn đông khách không?
[BROLL] Cận cảnh pha chế trà sữa trân châu hoàng kim bốc khói đá lạnh.
Hương vị đậm đà nguyên bản từ lá trà tươi hữu cơ tuyển chọn.
[BROLL] Khách hàng tươi cười thưởng thức ly nước thơm ngon.
Ưu đãi giảm 30% cho khách hàng ghé quán tuần này!`;
    if (dirEl) dirEl.value = `Hook: TRÀ SỮA ĐẬM VỊ ĐÔNG KHÁCH
CTA: GHÉ QUÁN NHẬN NGAY ƯU ĐÃI 30%
Pacing: 2.5s
Phong cách: F&B ấm áp tươi sáng, cận cảnh topping`;
  } else if (type === 'retail') {
    txt.value = `Chiếc máy xay cầm tay mini giải cứu mọi bữa ăn nhanh cho người bận rộn.
[BROLL] Cận cảnh lưỡi dao inox 304 quay tốc độ cao xay nhuyễn hạt và hoa quả.
Thiết kế không dây nhỏ gọn, sạc Type-C dùng cả tuần.
[BROLL] Rót sinh tố thơm mịn ra ly cực kỳ bắt mắt.
Đặt hàng ngay hôm nay để nhận ưu đãi miễn phí giao hàng toàn quốc!`;
    if (dirEl) dirEl.value = `Hook: MÁY XAY MINI SIÊU TIỆN LỢI
CTA: BẤM MUA NGAY ĐỂ FREE SHIP
Pacing: 2.0s
Phong cách: Commercial sắc nét, chi tiết công năng`;
  } else {
    txt.value = `Sản phẩm đỉnh cao với công nghệ hoàn toàn mới năm 2026.
[BROLL] Góc quay cận cảnh chi tiết thiết kế kim loại nguyên khối sang trọng.
Độ bền vượt trội, trải nghiệm mượt mà không độ trễ.
[BROLL] Sử dụng thực tế trong công việc hàng ngày vô cùng tiện lợi.
Bấm vào giỏ hàng bên dưới để sở hữu ngay giá tốt nhất!`;
    if (dirEl) dirEl.value = `Hook: CÔNG NGHỆ ĐỘT PHÁ MỚI
CTA: BẤM VÀO GIỎ HÀNG NGAY
Pacing: 2.5s
Phong cách: Hiện đại, công nghệ, mượt mà`;
  }
}

// Mẫu nhanh cho Yêu cầu đạo diễn
function fillDirectorSample(type) {
  const dirEl = document.getElementById('inputDirectorPrompt');
  if (!dirEl) return;

  if (type === 'fb') {
    dirEl.value = `Hook: TRÀ SỮA ĐẬM VỊ ĐÔNG KHÁCH
CTA: GHÉ QUÁN NHẬN NGAY ƯU ĐÃI 30%
Pacing: 2.5s
Phong cách: F&B ấm áp tươi sáng, cận cảnh bốc khói đá lạnh`;
  } else if (type === 'retail') {
    dirEl.value = `Hook: MÁY XAY MINI SIÊU TIỆN LỢI
CTA: BẤM MUA NGAY ĐỂ FREE SHIP
Pacing: 2.0s
Phong cách: Commercial sắc nét, chi tiết công năng dao xoay`;
  } else if (type === 'fast') {
    if (dirEl.value.includes('Pacing:')) {
      dirEl.value = dirEl.value.replace(/Pacing:[^\n]*/i, 'Pacing: 1.5s (Commercial Hook)');
    } else {
      dirEl.value = (dirEl.value.trim() ? dirEl.value.trim() + '\n' : '') + 'Pacing: 1.5s';
    }
  } else if (type === 'medium') {
    if (dirEl.value.includes('Pacing:')) {
      dirEl.value = dirEl.value.replace(/Pacing:[^\n]*/i, 'Pacing: 2.5s (Tiêu chuẩn)');
    } else {
      dirEl.value = (dirEl.value.trim() ? dirEl.value.trim() + '\n' : '') + 'Pacing: 2.5s';
    }
  }
}

// Ghi log vào Terminal Live
function logTerminal(msg) {
  const body = document.getElementById('termLiveLog');
  if (!body) return;
  const now = new Date();
  const timeStr = now.toTimeString().split(' ')[0];
  const line = document.createElement('div');
  line.textContent = `[${timeStr}] ${msg}`;
  body.appendChild(line);
  body.scrollTop = body.scrollHeight;
}

// Biên dịch dự án 13 Lớp qua MCP và kích hoạt CapCut Desktop
async function triggerCompile() {
  const projName = document.getElementById('inputProjectName')?.value.trim();
  const brollFolder = document.getElementById('inputBrollFolder')?.value.trim();
  const supportingFolder = document.getElementById('inputSupportingFolder')?.value.trim();
  const vjVideo = document.getElementById('inputVjVideo')?.value.trim();
  const bgmPath = document.getElementById('inputBgmPath')?.value.trim();
  const rawScript = document.getElementById('inputRawScript')?.value.trim();
  const directorRaw = document.getElementById('inputDirectorPrompt')?.value.trim() || '';
  const { hook: hookText, cta: ctaText, pacing: pacingMode } = parseDirectorRequirements(directorRaw);
  const autoOpenCapcut = document.getElementById('chkAutoOpenCapcut')?.checked;

  if (!projName) {
    showToast('Vui lòng nhập Tên Dự Án', 'warn');
    return;
  }
  if (!rawScript) {
    showToast('Vui lòng nhập kịch bản phân cảnh', 'warn');
    return;
  }

  const btn = document.getElementById('btnCompile');
  btn.disabled = true;
  btn.innerHTML = '<span class="scanner-spinner"></span> Đang phân tích kịch bản & biên dịch 13 lớp...';

  logTerminal(`[MCP-AI] Khởi chạy biên dịch dự án "${projName}"...`);
  logTerminal(`[AI-SCRIPT] Đang bóc tách phân cảnh và timecode theo nhịp "${pacingMode.toUpperCase()}"...`);

  try {
    // 1. Phân tích kịch bản qua AI Agent
    const parseRes = await fetch('/api/ai-agent/parse-script', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ raw_script: rawScript, pacing_mode: pacingMode })
    });
    const parseData = await parseRes.json();
    if (!parseData.ok) {
      throw new Error(parseData.detail || 'Không thể bóc tách kịch bản');
    }
    logTerminal(`[AI-SCRIPT] ✓ Bóc tách thành công ${parseData.count} câu phân cảnh thoại & B-Roll.`);

    // 2. Biên dịch 13 Layer qua MCP
    logTerminal(`[MCP-BUILD] Đang phân tầng VJ, Zero-Duplicate B-Roll, BGM Ducking, Subtitle Montserrat...`);
    const compileRes = await fetch('/api/mcp/create-project', {
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
        excludedClipPaths: [],
        scriptSentences: parseData.sentences
      })
    });
    const compileData = await compileRes.json();
    if (!compileData.ok) {
      throw new Error(compileData.error || 'Biên dịch MCP thất bại');
    }

    logTerminal(`[MCP-SUCCESS] ✓ Dự án "${compileData.projectName}" đã được tạo & nạp vào CapCut!`);
    showToast(`✓ Đã tạo thành công dự án 13 lớp: "${compileData.projectName}"!`, 'success');

    // 3. Tự động mở CapCut Desktop nếu được bật
    if (autoOpenCapcut) {
      logTerminal(`[CAPCUT-DESKTOP] 🎬 Đang nạp và kích hoạt Timeline CapCut Desktop...`);
      fetch('/api/capcut/open-project', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ projectName: compileData.projectName })
      }).then(r => r.json()).then(oRes => {
        if (oRes.ok) {
          logTerminal(`[CAPCUT-DESKTOP] ✓ Đã mở timeline CapCut Desktop thành công!`);
        } else {
          logTerminal(`[CAPCUT-DESKTOP] ℹ ${oRes.message || 'CapCut đã nạp.'}`);
        }
      }).catch(e => {
        logTerminal(`[CAPCUT-DESKTOP] Lưu ý: ${e.message}`);
      });
    }

    // 4. Cập nhật danh sách dự án
    await loadProjects(true);

  } catch (err) {
    logTerminal(`[MCP-ERR] Lỗi: ${err.message}`);
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>🚀</span> BIÊN DỊCH DỰ ÁN 13 LỚP & MỞ CAPCUT DESKTOP';
  }
}

// Quét lọc lỗi footage thư mục B-Roll
async function runFootageAnalysis() {
  const folder = document.getElementById('inputBrollFolder')?.value.trim();
  if (!folder) {
    showToast('Vui lòng nhập đường dẫn thư mục Footage B-Roll', 'warn');
    return;
  }
  showToast('Đang quét lọc lỗi footage qua AI & OpenCV...', 'info');
  logTerminal(`[AI-FOOTAGE] Khởi động AI Agent & OpenCV quét chẩn đoán folder: "${folder}"...`);

  try {
    const res = await fetch('/api/ai-agent/analyze-footage-folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder_path: folder, max_files: 25 })
    });
    const data = await res.json();
    if (data.ok) {
      logTerminal(`[AI-FOOTAGE] ✓ Quét xong: ${data.total_scanned} clip (Đạt: ${data.approved_count}, Cảnh báo: ${data.warning_count}, Loại: ${data.rejected_count})`);
      openFootageAuditModal(data);
    } else {
      logTerminal(`[AI-FOOTAGE] Lỗi: ${data.detail || data.message || 'Không thể quét'}`);
      showToast(data.detail || data.message || 'Không thể quét', 'error');
    }
  } catch (err) {
    logTerminal(`[AI-FOOTAGE] Lỗi kết nối: ${err.message}`);
    showToast(`Lỗi: ${err.message}`, 'error');
  }
}

// Quét lỗi footage của dự án cụ thể từ Tab 2
async function scanProjectFootage(projectName) {
  showToast(`Đang quét kiểm tra footage của dự án "${projectName}"...`, 'info');
  try {
    const projRes = await fetch(`/api/project/${encodeURIComponent(projectName)}`);
    if (!projRes.ok) throw new Error('Không thể đọc thông tin dự án');
    const pData = await projRes.json();
    const mats = pData.materials?.videos || [];
    if (mats.length === 0) {
      showToast('Dự án này chưa có video footage nào.', 'warn');
      return;
    }
    const firstVid = mats[0]._resolved_path || mats[0].path || '';
    const folder = firstVid ? firstVid.substring(0, firstVid.lastIndexOf('/')) : '';
    if (folder) {
      const res = await fetch('/api/ai-agent/analyze-footage-folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder_path: folder, max_files: 25 })
      });
      const data = await res.json();
      if (data.ok) {
        openFootageAuditModal(data);
      }
    } else {
      showToast('Không xác định được thư mục footage của dự án', 'warn');
    }
  } catch (err) {
    showToast(`Lỗi: ${err.message}`, 'error');
  }
}

// Mở Modal Báo Cáo Lọc Lỗi Footage
function openFootageAuditModal(data) {
  const modal = document.getElementById('modalFootageAudit');
  if (!modal) return;

  document.getElementById('auditScannedCount').textContent = data.total_scanned || 0;
  document.getElementById('auditApprovedCount').textContent = data.approved_count || 0;
  document.getElementById('auditWarningCount').textContent = data.warning_count || 0;
  document.getElementById('auditRejectedCount').textContent = data.rejected_count || 0;

  const note = document.getElementById('auditSummaryNote');
  if (note) {
    note.innerHTML = `
      AI Agent đã hoàn tất quét <b>${data.total_scanned} clip</b>. 
      Đạt chuẩn thương mại: <b>${data.approved_count}</b> clip. 
      Clip có vấn đề (rung lắc, mờ, cháy sáng): <b>${data.rejected_count}</b> clip. 
      Hệ thống sẽ tự động ưu tiên các clip đạt chuẩn khi nạp vào timeline 13 lớp!
    `;
  }

  const list = document.getElementById('auditClipsList');
  if (list && data.analyzed_clips) {
    list.innerHTML = data.analyzed_clips.map(c => {
      const bClass = c.status === 'approved' ? 'approved' : (c.status === 'warning' ? 'warning' : 'rejected');
      const bText = c.status === 'approved' ? 'Đạt chuẩn' : (c.status === 'warning' ? 'Cảnh báo' : 'Loại trừ');
      const reason = c.reject_reason ? ` • ${esc(c.reject_reason)}` : '';
      return `
        <div class="hub-audit-item">
          <div class="item-name" title="${esc(c.file_name)}">${esc(c.file_name)} <span style="font-size:11px;color:#94a3b8;">${reason}</span></div>
          <span class="audit-badge ${bClass}">${bText}</span>
        </div>
      `;
    }).join('');
  }

  modal.classList.add('active');
}

// Đóng Modal Báo Cáo Lọc Lỗi
function closeFootageAuditModal(event) {
  if (event && event.target && event.target !== event.currentTarget) return;
  const modal = document.getElementById('modalFootageAudit');
  if (modal) modal.classList.remove('active');
}

// Khởi chạy khi load trang
window.addEventListener('DOMContentLoaded', () => {
  generateRandomProjectName();
  fillSampleScript('fb');
  loadProjects();
});
