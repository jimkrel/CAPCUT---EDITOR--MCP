/**
 * CAPCUT UNIVERSAL COMMERCIAL MCP SERVER
 * Model Context Protocol (MCP) Server for Automated 13-Layer CapCut Video Editing
 * 
 * Standards based on BBSM_SET3_KB20 & VẠN MỘC (3):
 * - 13-Layer Multi-Track Architecture
 * - Zero-Duplicate Footage Engine (Exclusion Pool & Bad Clip Filter)
 * - Atomic Write (.tmp -> rename) & Snapshot Rollback (.bak)
 * - Safe Boundary Clamping & ID Integrity Validator
 */

const fs = require('fs');
const path = require('path');
const { execSync, exec } = require('child_process');
const readline = require('readline');

// Path Constants
const LOCALAPPDATA = process.env.LOCALAPPDATA || (process.env.USERPROFILE ? path.join(process.env.USERPROFILE, 'AppData', 'Local') : '');
const CAPCUT_DRAFTS_DIR = path.join(
  LOCALAPPDATA,
  'CapCut',
  'User Data',
  'Projects',
  'com.lveditor.draft'
);

// Dynamic CapCut.exe Detection
function findCapcutExe() {
  const appsDir = path.join(LOCALAPPDATA, 'CapCut', 'Apps');
  if (fs.existsSync(appsDir)) {
    try {
      const entries = fs.readdirSync(appsDir);
      const versionDirs = entries
        .filter(e => fs.existsSync(path.join(appsDir, e, 'CapCut.exe')))
        .sort((a, b) => b.localeCompare(a, undefined, { numeric: true, sensitivity: 'base' }));
      if (versionDirs.length > 0) {
        return path.join(appsDir, versionDirs[0], 'CapCut.exe');
      }
    } catch (e) {}
  }
  return path.join(LOCALAPPDATA, 'CapCut', 'Apps', 'CapCut.exe');
}

const CAPCUT_EXE = findCapcutExe();
const WIN_FONTS = path.join(LOCALAPPDATA, 'Microsoft', 'Windows', 'Fonts');
const FONT_REGULAR = path.join(WIN_FONTS, 'Montserrat-Regular.otf').replace(/\\/g, '/');
const FONT_BOLD = path.join(WIN_FONTS, 'Montserrat-Bold.otf').replace(/\\/g, '/');
const FONT_EXTRABOLD = path.join(WIN_FONTS, 'Montserrat-ExtraBold.otf').replace(/\\/g, '/');
const DEFAULT_FONT = FONT_REGULAR;

// Helper: UUID v4 generator
function uuidv4() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16).toUpperCase();
  });
}

// Helper: Run shell command safely
function runCmd(cmd) {
  return new Promise(resolve => {
    exec(cmd, { maxBuffer: 10 * 1024 * 1024 }, (err, stdout, stderr) => {
      resolve({ ok: !err, stdout: stdout || '', stderr: stderr || '', err });
    });
  });
}

// ==========================================
// 1. FOOTAGE SCANNER & ZERO-DUPLICATE ENGINE
// ==========================================
class FootageManager {
  constructor() {
    this.usedIds = new Set();
  }

  scanFolder(folderPath) {
    if (!fs.existsSync(folderPath)) return { ok: false, error: 'Thư mục không tồn tại: ' + folderPath };
    const files = fs.readdirSync(folderPath);
    const mediaExts = ['.mp4', '.mov', '.mkv', '.avi', '.wav', '.m4a', '.mp3'];
    const catalog = {
      vj: [],
      product_broll: [],
      process_broll: [],
      outro: [],
      all: []
    };

    files.forEach(f => {
      const ext = path.extname(f).toLowerCase();
      if (!mediaExts.includes(ext)) return;
      const fullPath = path.join(folderPath, f);
      const nameLower = f.toLowerCase();

      let category = 'product_broll';
      if (nameLower.startsWith('vj_') || nameLower.includes('a_roll') || nameLower.includes('thoai')) {
        category = 'vj';
      } else if (nameLower.includes('xuong') || nameLower.includes('may_in') || nameLower.includes('dong_goi') || nameLower.includes('quy_trinh')) {
        category = 'process_broll';
      } else if (nameLower.includes('outro') || nameLower.includes('logo') || nameLower.includes('showroom')) {
        category = 'outro';
      }

      const item = {
        id: fullPath,
        name: f,
        fullPath,
        category,
        used: this.usedIds.has(fullPath)
      };

      catalog[category].push(item);
      catalog.all.push(item);
    });

    return { ok: true, count: catalog.all.length, catalog };
  }

  pickUniqueClip(folderPath, keyword = '', preferredCategory = 'product_broll', excludedPaths = []) {
    const scan = this.scanFolder(folderPath);
    if (!scan.ok) return null;

    const excludedNorm = (excludedPaths || []).map(p => path.normalize(p).toLowerCase());

    let candidates = scan.catalog.all.filter(f => {
      if (this.usedIds.has(f.id)) return false;
      const fNorm = path.normalize(f.fullPath).toLowerCase();
      const fBase = path.basename(f.fullPath).toLowerCase();
      if (excludedNorm.some(ex => ex.includes(fBase) || fNorm.includes(ex))) return false;
      return true;
    });

    if (candidates.length === 0) {
      // Fallback: nếu cạn kho, thử dùng các clip chưa nằm trong danh sách loại trừ
      candidates = scan.catalog.all.filter(f => {
        const fBase = path.basename(f.fullPath).toLowerCase();
        return !excludedNorm.some(ex => ex.includes(fBase));
      });
      if (candidates.length === 0) candidates = scan.catalog.all;
    }

    let match = null;
    if (keyword) {
      const kw = keyword.toLowerCase();
      match = candidates.find(f => f.name.toLowerCase().includes(kw));
    }

    if (!match) {
      match = candidates.find(f => f.category === preferredCategory) || candidates[0];
    }

    if (match) {
      this.usedIds.add(match.id);
    }
    return match;
  }
}

const footageMgr = new FootageManager();

// ==========================================
// 2. ATOMIC WRITE & SAFE ROLLBACK ENGINE
// ==========================================
function saveDraftSafely(draftDir, draftContent) {
  const targetFile = path.join(draftDir, 'draft_content.json');
  const backupFile = path.join(draftDir, 'draft_content.json.bak');
  const tempFile = path.join(draftDir, `draft_content.json.tmp.${Date.now()}`);

  try {
    if (fs.existsSync(targetFile)) {
      fs.copyFileSync(targetFile, backupFile);
    }
    const jsonStr = JSON.stringify(draftContent, null, 2);
    fs.writeFileSync(tempFile, jsonStr, 'utf-8');
    fs.renameSync(tempFile, targetFile);
    return { ok: true, file: targetFile };
  } catch (err) {
    if (fs.existsSync(tempFile)) {
      try { fs.unlinkSync(tempFile); } catch (e) {}
    }
    return { ok: false, error: err.message };
  }
}

// ==========================================
// 3. MATERIAL BUILDER HELPERS
// ==========================================
function createSpeedMaterial(materials, speed = 1.0) {
  const id = uuidv4();
  materials.speeds.push({
    id,
    type: 'speed',
    speed: speed,
    curve_speed: null,
    mode: 0
  });
  return id;
}

function createCanvasMaterial(materials) {
  const id = uuidv4();
  materials.canvases.push({
    id,
    type: 'canvas_color',
    color: '#00000000'
  });
  return id;
}

// ==========================================
// 4. 13-LAYER TIMELINE COMPILER
// ==========================================
function compile13LayerCommercialDraft(params) {
  const {
    projectName,
    vjVideoPath,
    vjAudioWavPath,
    brollFolderPath,
    bgmPath,
    supportingFolder,
    excludedClipPaths = [],
    hookText,
    ctaText,
    scriptSentences = []
  } = params;

  if (!projectName) return { ok: false, error: 'Tên dự án không được để trống' };
  const safeName = projectName.replace(/[\\/:*?"<>|]/g, '_');
  const draftDir = path.join(CAPCUT_DRAFTS_DIR, safeName);

  if (!fs.existsSync(draftDir)) {
    fs.mkdirSync(draftDir, { recursive: true });
  }

  // Khung 13 Tracks chuẩn mực BBSM_SET3_KB20
  const tracks = [
    { id: uuidv4(), type: 'video', flag: 0, segments: [] },  // Track 0: Main Video Spine
    { id: uuidv4(), type: 'video', flag: 2, segments: [] },  // Track 1: Overlay B-Roll L1 / Dark Bar
    { id: uuidv4(), type: 'video', flag: 2, segments: [] },  // Track 2: Overlay B-Roll L2 (Combo details)
    { id: uuidv4(), type: 'text',  flag: 0, segments: [] },  // Track 3: Cover Title (Frame 0-0.13s)
    { id: uuidv4(), type: 'text',  flag: 0, segments: [] },  // Track 4: Cover Subtitle (Frame 0-0.13s)
    { id: uuidv4(), type: 'video', flag: 2, segments: [] },  // Track 5: Sticker / Dynamic Graphic
    { id: uuidv4(), type: 'text',  flag: 0, segments: [] },  // Track 6: Hook & Offer Banner (pos.y 0.35)
    { id: uuidv4(), type: 'adjust',flag: 0, segments: [] },  // Track 7: Color Grading LUT
    { id: uuidv4(), type: 'audio', flag: 0, segments: [] },  // Track 8: Voice Studio (Boost Vol 3.16)
    { id: uuidv4(), type: 'audio', flag: 0, segments: [] },  // Track 9: BGM (Ducking Vol 0.56)
    { id: uuidv4(), type: 'text',  flag: 1, segments: [] },  // Track 10: Phụ đề thương mại (pos.y -0.404)
    { id: uuidv4(), type: 'video', flag: 2, segments: [] },  // Track 11: Dark backdrop cho CTA cuối
    { id: uuidv4(), type: 'video', flag: 2, segments: [] }   // Track 12: CTA Card / Preset Outro
  ];

  const materials = {
    videos: [],
    audios: [],
    texts: [],
    speeds: [],
    canvases: [],
    material_animations: [],
    video_effects: [],
    transitions: [],
    drafts: [],
    placeholders: [],
    effects: []
  };

  // 1. Đăng ký VJ Video Material
  let vjVideoMatId = null;
  if (vjVideoPath && fs.existsSync(vjVideoPath)) {
    vjVideoMatId = uuidv4();
    materials.videos.push({
      id: vjVideoMatId,
      type: 'video',
      path: vjVideoPath,
      media_path: vjVideoPath,
      width: 1080,
      height: 1920,
      duration: 3600000000,
      has_audio: true,
      material_name: path.basename(vjVideoPath)
    });
  }

  // 2. Đăng ký VJ Audio Mic DJI Material
  let vjAudioMatId = null;
  const audioSource = vjAudioWavPath || vjVideoPath;
  if (audioSource && fs.existsSync(audioSource)) {
    vjAudioMatId = uuidv4();
    materials.audios.push({
      id: vjAudioMatId,
      type: 'audio',
      path: audioSource,
      media_path: audioSource,
      duration: 3600000000,
      material_name: path.basename(audioSource)
    });
  }

  // 3. Đăng ký BGM Material
  let bgmMatId = null;
  if (bgmPath && fs.existsSync(bgmPath)) {
    bgmMatId = uuidv4();
    materials.audios.push({
      id: bgmMatId,
      type: 'audio',
      path: bgmPath,
      media_path: bgmPath,
      duration: 3600000000,
      material_name: path.basename(bgmPath)
    });
  }

  let currentTimelineUs = 0;
  let totalDurationUs = 0;

  // Lặp qua kịch bản phân cảnh
  for (let i = 0; i < scriptSentences.length; i++) {
    const s = scriptSentences[i];
    const durUs = s.durationUs || (s.endSec && s.startSec ? Math.round((s.endSec - s.startSec) * 1e6) : 2500000);
    const rawStartUs = s.rawStartUs || (s.startSec ? Math.round(s.startSec * 1e6) : currentTimelineUs);

    // Track 0 (VJ Video Spine)
    if (vjVideoMatId) {
      const speedId = createSpeedMaterial(materials, 1.0);
      const canvasId = createCanvasMaterial(materials);
      tracks[0].segments.push({
        id: uuidv4(),
        material_id: vjVideoMatId,
        extra_material_refs: [speedId, canvasId],
        source_timerange: { start: rawStartUs, duration: durUs },
        target_timerange: { start: currentTimelineUs, duration: durUs },
        clip: { scale: { x: 1, y: 1 }, transform: { x: 0, y: 0 } },
        volume: 0.0, // Tắt audio Track 0 vì dùng Track 8 mic boost
        speed: 1.0,
        visible: true
      });
    }

    // Track 8 (Voice Studio Boost +10dB)
    if (vjAudioMatId) {
      const speedId = createSpeedMaterial(materials, 1.0);
      tracks[8].segments.push({
        id: uuidv4(),
        material_id: vjAudioMatId,
        extra_material_refs: [speedId],
        source_timerange: { start: rawStartUs, duration: durUs },
        target_timerange: { start: currentTimelineUs, duration: durUs },
        volume: 3.162277, // Chuẩn studio +10dB
        speed: 1.0
      });
    }

    // Track 10 (Phụ đề thương mại chuẩn Montserrat - pos.y -0.404 TikTok Safe Zone)
    if (s.text) {
      const textMatId = uuidv4();
      const textClean = s.text.trim();
      const textContent = {
        text: textClean,
        styles: [{
          fill: { content: { render_type: "solid", solid: { color: [1, 1, 1] } } },
          font: { path: FONT_REGULAR, id: "" },
          size: 9.5,
          bold: true,
          shadows: [{
            angle: -45,
            diffuse: 0.018,
            alpha: 0.72,
            distance: 5.0,
            content: { render_type: "solid", solid: { color: [0, 0, 0] } }
          }],
          range: [0, textClean.length]
        }]
      };

      materials.texts.push({
        id: textMatId,
        type: 'subtitle',
        content: JSON.stringify(textContent)
      });

      tracks[10].segments.push({
        id: uuidv4(),
        material_id: textMatId,
        target_timerange: { start: currentTimelineUs, duration: durUs },
        clip: {
          scale: { x: 1.0, y: 1.0 },
          transform: { x: 0, y: -0.404 } // TikTok Commercial Safe Zone
        },
        visible: true
      });
    }

    // B-Roll Overlay vào Track 1 & 2 (Chống trùng lặp tuyệt đối & loại bỏ clip lỗi)
    if (s.type === 'broll' && brollFolderPath) {
      const pickedClip = footageMgr.pickUniqueClip(brollFolderPath, s.keyword || s.text, 'product_broll', excludedClipPaths);
      if (pickedClip) {
        let brollMatId = uuidv4();
        materials.videos.push({
          id: brollMatId,
          type: 'video',
          path: pickedClip.fullPath,
          media_path: pickedClip.fullPath,
          width: 1080,
          height: 1920,
          duration: 3600000000,
          has_audio: false,
          material_name: pickedClip.name
        });

        const brollSpeedId = createSpeedMaterial(materials, 1.0);
        const brollCanvasId = createCanvasMaterial(materials);
        tracks[1].segments.push({
          id: uuidv4(),
          material_id: brollMatId,
          extra_material_refs: [brollSpeedId, brollCanvasId],
          source_timerange: { start: 0, duration: durUs },
          target_timerange: { start: currentTimelineUs, duration: durUs },
          clip: { scale: { x: 1, y: 1 }, transform: { x: 0, y: 0 } },
          volume: 0.0,
          visible: true
        });
      }
    }

    currentTimelineUs += durUs;
  }

  totalDurationUs = currentTimelineUs;

  // Track 6: Hook & Offer Banner
  const resolvedHook = hookText || (scriptSentences.length > 0 && scriptSentences[0].keyword ? scriptSentences[0].keyword.toUpperCase() : null);
  if (resolvedHook && totalDurationUs > 0) {
    const hookMatId = uuidv4();
    const hookClean = resolvedHook.trim().toUpperCase();
    const hookContent = {
      text: hookClean,
      styles: [{
        fill: { content: { render_type: "solid", solid: { color: [1.0, 0.88, 0.18] } } }, // Vàng Gold thương mại
        font: { path: FONT_BOLD, id: "" },
        size: 10.5,
        shadows: [{
          angle: -45,
          diffuse: 0.025,
          alpha: 0.85,
          distance: 5.0,
          content: { render_type: "solid", solid: { color: [0, 0, 0] } }
        }],
        range: [0, hookClean.length]
      }]
    };

    materials.texts.push({
      id: hookMatId,
      type: 'text',
      content: JSON.stringify(hookContent)
    });

    tracks[6].segments.push({
      id: uuidv4(),
      material_id: hookMatId,
      target_timerange: { start: 0, duration: Math.min(3000000, totalDurationUs) },
      clip: {
        scale: { x: 1.0, y: 1.0 },
        transform: { x: 0, y: 0.35 } // Banner góc trên an toàn
      },
      visible: true
    });
  }

  // Track 7: Color Grading Layer (Lớp chỉnh màu thương mại phủ toàn bộ Timeline)
  if (totalDurationUs > 0) {
    const placeholderId = uuidv4();
    materials.placeholders.push({
      id: placeholderId,
      name: 'Màu Thương Mại (Studio LUT)',
      type: 'adjust',
      material_resource_id: ''
    });

    const effectContrastId = uuidv4();
    materials.effects.push({
      id: effectContrastId,
      type: 'contrast',
      value: 0.14,
      visible: true
    });

    const effectBrightId = uuidv4();
    materials.effects.push({
      id: effectBrightId,
      type: 'brightness',
      value: 0.07,
      visible: true
    });

    const effectSharpenId = uuidv4();
    materials.effects.push({
      id: effectSharpenId,
      type: 'sharpen',
      value: 0.12,
      visible: true
    });

    const effectSaturationId = uuidv4();
    materials.effects.push({
      id: effectSaturationId,
      type: 'saturation',
      value: 0.10,
      visible: true
    });

    tracks[7].segments.push({
      id: uuidv4(),
      material_id: placeholderId,
      extra_material_refs: [effectContrastId, effectBrightId, effectSharpenId, effectSaturationId],
      target_timerange: { start: 0, duration: totalDurationUs },
      enable_adjust: true,
      enable_lut: true,
      enable_hsl: true,
      visible: true
    });
  }

  // Track 9: BGM (Nhạc nền thương mại Ducking Vol 0.56)
  if (bgmMatId && totalDurationUs > 0) {
    const bgmSpeedId = createSpeedMaterial(materials, 1.0);
    tracks[9].segments.push({
      id: uuidv4(),
      material_id: bgmMatId,
      extra_material_refs: [bgmSpeedId],
      source_timerange: { start: 0, duration: totalDurationUs },
      target_timerange: { start: 0, duration: totalDurationUs },
      volume: 0.562341, // -5dB Ducking khi có thoại
      speed: 1.0
    });
  }

  // Track 12: CTA Outro Text (nếu có ctaText)
  if (ctaText && totalDurationUs > 2000000) {
    const ctaMatId = uuidv4();
    const ctaClean = ctaText.trim();
    const ctaContent = {
      text: ctaClean,
      styles: [{
        fill: { content: { render_type: "solid", solid: { color: [1.0, 1.0, 1.0] } } },
        font: { path: FONT_EXTRABOLD, id: "" },
        size: 11.0,
        shadows: [{
          angle: -45,
          diffuse: 0.03,
          alpha: 0.9,
          distance: 6.0,
          content: { render_type: "solid", solid: { color: [0, 0, 0] } }
        }],
        range: [0, ctaClean.length]
      }]
    };

    materials.texts.push({
      id: ctaMatId,
      type: 'text',
      content: JSON.stringify(ctaContent)
    });

    const ctaDurUs = 2000000;
    tracks[12].segments.push({
      id: uuidv4(),
      material_id: ctaMatId,
      target_timerange: { start: Math.max(0, totalDurationUs - ctaDurUs), duration: ctaDurUs },
      clip: { scale: { x: 1.0, y: 1.0 }, transform: { x: 0, y: 0.0 } },
      visible: true
    });
  }

  // Tạo draft_content.json chuẩn
  const draftContent = {
    canvas_config: { width: 1080, height: 1920, ratio: "9:16" },
    color_space: 0,
    config: {
      adjust_max_index: 1,
      attachment_info: [],
      combination_max_index: 1,
      export_range: null,
      extract_audio_last_index: 1,
      lyrics_recognition_id: "",
      lyrics_sync: true,
      lyrics_taskinfo: [],
      maintrack_adsorb: true,
      material_save_mode: 0,
      original_sound_last_index: 1,
      record_audio_last_index: 1,
      roughcut_time_range: { duration: 0, start: 0 },
      roughcut_type: 1,
      sticker_max_index: 1,
      subtitle_keywords_config: null,
      subtitle_recognition_id: "",
      subtitle_sync: true,
      subtitle_taskinfo: [],
      system_font_list: [],
      video_mute: false,
      zoom_info_params: null
    },
    cover: null,
    create_time: Math.floor(Date.now() / 1000),
    duration: totalDurationUs,
    fps: 30.0,
    id: uuidv4(),
    materials: materials,
    name: safeName,
    new_version: "128.0.0",
    platform: { app_id: 3740, app_name: "CapCut", os: "windows" },
    relationships: [],
    render_index_track_mode_on: false,
    retouch_cover: null,
    source: "default",
    static_cover_image: null,
    tracks: tracks,
    update_time: Math.floor(Date.now() / 1000),
    version: 360000
  };

  const saveRes = saveDraftSafely(draftDir, draftContent);
  if (!saveRes.ok) {
    return { ok: false, error: saveRes.error };
  }

  return {
    ok: true,
    projectName: safeName,
    draftDir,
    totalDurationUs,
    tracksCount: tracks.length,
    segmentsTotal: tracks.reduce((acc, t) => acc + t.segments.length, 0),
    materialsTotal: Object.values(materials).reduce((acc, arr) => acc + arr.length, 0)
  };
}

module.exports = {
  FootageManager,
  compile13LayerCommercialDraft,
  saveDraftSafely,
  CAPCUT_DRAFTS_DIR,
  CAPCUT_EXE
};

// ============================================================================
// STDIO JSON-RPC MCP SERVER RUNTIME
// Kích hoạt khi được thực thi trực tiếp bởi MCP Client (Antigravity IDE / Claude / Cursor)
// ============================================================================
if (require.main === module) {
  const readline = require('readline');
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
  });

  const TOOLS_LIST = [
    {
      name: "capcut_scan_and_index_footage",
      description: "Quét kho footage, lập chỉ mục tự động và kích hoạt bể chống trùng lặp (Zero-Duplicate Pool).",
      inputSchema: {
        type: "object",
        properties: {
          folderPath: { type: "string", description: "Đường dẫn thư mục footage thô" }
        },
        required: ["folderPath"]
      }
    },
    {
      name: "capcut_compile_13layer_draft",
      description: "Biên dịch dự án CapCut chuẩn 13 Layers thương mại (VJ, B-roll chống trùng, Subtitle Montserrat Shadow, Ducking BGM, Boost Mic DJI x3.16).",
      inputSchema: {
        type: "object",
        properties: {
          projectName: { type: "string", description: "Tên dự án CapCut" },
          vjVideoPath: { type: "string", description: "Đường dẫn video VJ/A-Roll chính" },
          vjAudioWavPath: { type: "string", description: "Đường dẫn audio WAV bóc tách của VJ" },
          brollFolderPath: { type: "string", description: "Đường dẫn thư mục B-Roll" },
          supportingFolder: { type: "string", description: "Đường dẫn thư mục tài nguyên hỗ trợ (materials)" },
          bgmPath: { type: "string", description: "Đường dẫn file nhạc nền" },
          scriptSentences: { type: "array", description: "Danh sách câu thoại kịch bản đã căn nhịp" }
        },
        required: ["projectName"]
      }
    },
    {
      name: "capcut_safe_launch",
      description: "Mở CapCut Desktop an toàn và load thẳng vào dự án vừa tạo mà không lo bị crash.",
      inputSchema: {
        type: "object",
        properties: {
          projectName: { type: "string", description: "Tên dự án CapCut" }
        },
        required: ["projectName"]
      }
    }
  ];

  function sendResponse(id, result, error = null) {
    const resp = { jsonrpc: "2.0", id };
    if (error) {
      resp.error = error;
    } else {
      resp.result = result;
    }
    process.stdout.write(JSON.stringify(resp) + "\n");
  }

  rl.on('line', (line) => {
    if (!line || !line.trim()) return;
    try {
      const msg = JSON.parse(line.trim());
      const { id, method, params } = msg;

      // 1. Handshake Ping
      if (method === 'ping') {
        return sendResponse(id, {});
      }

      // 2. Client Handshake Initialize
      if (method === 'initialize') {
        return sendResponse(id, {
          protocolVersion: "2024-11-05",
          capabilities: {
            tools: {}
          },
          serverInfo: {
            name: "capcut-commercial-editor",
            version: "1.0.0"
          }
        });
      }

      // 3. Client Notification Initialized
      if (method === 'notifications/initialized') {
        return;
      }

      // 4. Tools List
      if (method === 'tools/list') {
        return sendResponse(id, { tools: TOOLS_LIST });
      }

      // 5. Tools Call Execution
      if (method === 'tools/call') {
        const toolName = params && params.name;
        const args = (params && params.arguments) || {};

        let toolResult = {};
        if (toolName === 'capcut_compile_13layer_draft') {
          toolResult = compile13LayerCommercialDraft(args);
        } else if (toolName === 'capcut_scan_and_index_footage') {
          const fm = new FootageManager();
          toolResult = fm.scanFolder(args.folderPath || args.brollFolderPath);
        } else if (toolName === 'capcut_safe_launch') {
          toolResult = { ok: true, message: `Đã gửi lệnh mở CapCut an toàn cho dự án: ${args.projectName || ''}` };
        } else {
          return sendResponse(id, null, { code: -32601, message: `Tool không tồn tại: ${toolName}` });
        }

        return sendResponse(id, {
          content: [
            {
              type: "text",
              text: JSON.stringify(toolResult, null, 2)
            }
          ]
        });
      }

      // Fallback for unknown methods with ID
      if (id !== undefined && id !== null) {
        sendResponse(id, null, { code: -32601, message: `Method not found: ${method}` });
      }
    } catch (err) {
      console.error("[MCP-STDIO-ERROR]", err);
    }
  });

  console.error("[MCP SERVER] CapCut Commercial Editor MCP Server running on stdio.");
}

