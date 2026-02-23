/**
 * Music Tab Finder - 前端互動邏輯
 * 處理 YouTube 轉譜請求、歷史/收藏管理與 PWA 功能。
 * 支援 GitHub Pages 靜態模式與本地 API 模式。
 */

// ── 設定 ──
// 動態偵測 API 位址，手機存取時自動使用電腦 IP
const API_BASE = window.location.origin;
const IS_GITHUB_PAGES = window.location.hostname.includes('github.io');
let currentType = 'chord_sheet';
let currentResult = null;
let allSheets = []; // GitHub Pages 模式下的所有樂譜

// ── 初始化 ──
document.addEventListener('DOMContentLoaded', () => {
    if (IS_GITHUB_PAGES) {
        initGitHubPagesMode();
    } else {
        initLocalMode();
    }

    // Enter 快捷鍵
    const urlInput = document.getElementById('youtube-url');
    if (urlInput) {
        urlInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                startTranscribe();
            }
        });
    }

    // URL hash 導航
    handleHashNavigation();
    window.addEventListener('hashchange', handleHashNavigation);
});

// ── GitHub Pages 模式初始化 ──
async function initGitHubPagesMode() {
    // 隱藏轉譜輸入區，顯示樂譜庫
    const heroSection = document.querySelector('.hero-section');
    const inputCard = document.querySelector('.input-card');
    const progressSection = document.getElementById('progress-section');

    if (heroSection) {
        heroSection.innerHTML = `
            <h1 class="hero-title">
                <span class="gradient-text">🎵 我的樂譜庫</span>
            </h1>
            <p class="hero-subtitle">所有已轉出的樂譜，隨時瀏覽、分享</p>
        `;
    }
    if (inputCard) inputCard.classList.add('hidden');
    if (progressSection) progressSection.classList.add('hidden');

    // 載入靜態樂譜資料
    try {
        const res = await fetch('data/sheets.json');
        if (res.ok) {
            allSheets = await res.json();
            renderSheetLibrary();
        } else {
            showEmptyLibrary();
        }
    } catch {
        showEmptyLibrary();
    }
}

// ── 本地模式初始化 ──
function initLocalMode() {
    // 正常模式，什麼都不需要做
}

// ── 渲染樂譜庫 (GitHub Pages 模式) ──
function renderSheetLibrary() {
    const resultSection = document.getElementById('result-section');
    const transcribeTab = document.getElementById('tab-transcribe');

    if (!allSheets || allSheets.length === 0) {
        showEmptyLibrary();
        return;
    }

    // 在轉譜頁面上方插入樂譜庫卡片
    let libraryHTML = '<div class="sheet-library">';
    const typeLabels = {
        chord_sheet: '🎤 彈唱簡譜',
        fingerstyle_tab: '🎸 指彈譜',
        piano_sheet: '🎹 鋼琴譜',
    };

    allSheets.forEach((sheet, idx) => {
        libraryHTML += `
        <div class="library-card glass-card" onclick="viewSheetFromLibrary(${idx})">
            <div class="library-card-header">
                <span class="library-card-title">${escapeHtml(sheet.title || '未知歌曲')}</span>
                <button class="action-btn share-mini-btn" onclick="event.stopPropagation(); shareSheet(${idx})" title="分享">
                    📤
                </button>
            </div>
            <div class="library-card-meta">
                <span class="record-type-tag">${typeLabels[sheet.output_type] || '樂譜'}</span>
                <span class="meta-tag">♩ = ${sheet.tempo || 120}</span>
                <span class="meta-tag">${sheet.key || 'C'} 調</span>
            </div>
            <div class="library-card-date">${formatDate(sheet.created_at)}</div>
        </div>`;
    });
    libraryHTML += '</div>';

    // 插入到合適的位置
    const insertTarget = document.querySelector('.input-card');
    if (insertTarget) {
        insertTarget.outerHTML = libraryHTML;
    } else {
        // fallback: 放在 hero 下方
        const hero = document.querySelector('.hero-section');
        if (hero) hero.insertAdjacentHTML('afterend', libraryHTML);
    }
}

// ── 顯示空樂譜庫 ──
function showEmptyLibrary() {
    const transcribeTab = document.getElementById('tab-transcribe');
    const inputCard = document.querySelector('.input-card');
    if (inputCard) inputCard.classList.add('hidden');

    const hero = document.querySelector('.hero-section');
    if (hero) {
        hero.insertAdjacentHTML('afterend', `
            <div class="empty-state">
                <span class="empty-icon">📭</span>
                <p>還沒有樂譜</p>
                <p class="empty-hint">在電腦端轉譜後，執行 deploy.bat 即可在此瀏覽</p>
            </div>
        `);
    }
}

// ── 從樂譜庫檢視 ──
function viewSheetFromLibrary(index) {
    const sheet = allSheets[index];
    if (!sheet) return;
    currentResult = sheet;
    displayResult(sheet);

    // 更新 URL hash
    if (sheet.id) {
        history.pushState(null, '', `#sheet-${sheet.id}`);
    }
}

// ── URL hash 導航 ──
function handleHashNavigation() {
    const hash = window.location.hash;
    if (!hash) return;

    // #sheet-{id} 格式
    const sheetMatch = hash.match(/^#sheet-(.+)$/);
    if (sheetMatch && allSheets.length > 0) {
        const sheetId = sheetMatch[1];
        const idx = allSheets.findIndex(s => s.id === sheetId);
        if (idx >= 0) {
            viewSheetFromLibrary(idx);
        }
    }

    // #share-{base64} 格式 - 解碼分享的樂譜
    const shareMatch = hash.match(/^#share-(.+)$/);
    if (shareMatch) {
        try {
            const data = JSON.parse(decodeURIComponent(atob(shareMatch[1])));
            currentResult = data;
            displayResult(data);
        } catch {
            showToast('無法解析分享連結');
        }
    }
}

// ── 分享功能 (QR Code) ──
function shareSheet(index) {
    const sheet = index !== undefined ? allSheets[index] : currentResult;
    if (!sheet) return;

    // 建立分享用的精簡資料
    const shareData = {
        title: sheet.title,
        content: sheet.content,
        tempo: sheet.tempo,
        key: sheet.key,
        output_type: sheet.output_type,
    };

    // 嘗試用 sheet ID 建立短連結（如果在 GitHub Pages 上）
    let shareUrl;
    if (IS_GITHUB_PAGES && sheet.id) {
        shareUrl = `${window.location.origin}${window.location.pathname}#sheet-${sheet.id}`;
    } else {
        // 編碼分享資料到 URL
        const encoded = btoa(encodeURIComponent(JSON.stringify(shareData)));
        const baseUrl = IS_GITHUB_PAGES
            ? `${window.location.origin}${window.location.pathname}`
            : window.location.href.split('#')[0];
        shareUrl = `${baseUrl}#share-${encoded}`;
    }

    showQRCodeModal(sheet.title || '樂譜', shareUrl);
}

function shareCurrentSheet() {
    if (!currentResult) return;
    shareSheet(undefined);
}

// ── QR Code Modal ──
function showQRCodeModal(title, url) {
    const modal = document.getElementById('qr-modal');
    const qrTitle = document.getElementById('qr-title');
    const qrImage = document.getElementById('qr-image');
    const qrLink = document.getElementById('qr-link');

    if (!modal) return;

    qrTitle.textContent = title;

    // 使用 QR Server API 產生 QR Code
    const qrApiUrl = `https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${encodeURIComponent(url)}&bgcolor=1e293b&color=f1f5f9`;
    qrImage.src = qrApiUrl;
    qrImage.alt = `QR Code - ${title}`;

    qrLink.textContent = url.length > 60 ? url.substring(0, 60) + '...' : url;
    qrLink.href = url;
    qrLink.dataset.fullUrl = url;

    modal.classList.remove('hidden');
}

function closeQRModal() {
    document.getElementById('qr-modal').classList.add('hidden');
}

async function copyShareLink() {
    const link = document.getElementById('qr-link');
    const url = link.dataset.fullUrl || link.href;
    try {
        await navigator.clipboard.writeText(url);
        showToast('📋 連結已複製！');
    } catch {
        const ta = document.createElement('textarea');
        ta.value = url;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        showToast('📋 連結已複製！');
    }
}

// ── 頁簽切換 ──
function switchTab(tabName) {
    document.querySelectorAll('.nav-tab').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    document.querySelectorAll('.tab-content').forEach(section => {
        section.classList.toggle('active', section.id === `tab-${tabName}`);
    });

    if (tabName === 'history') loadHistory();
    if (tabName === 'favorites') loadFavorites();
}

// ── 類型選擇 ──
function selectType(type) {
    currentType = type;
    document.querySelectorAll('.type-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.type === type);
    });
}

// ── 剪貼簿貼上 ──
async function pasteFromClipboard() {
    try {
        const text = await navigator.clipboard.readText();
        document.getElementById('youtube-url').value = text;
        showToast('已從剪貼簿貼上');
    } catch {
        showToast('無法存取剪貼簿');
    }
}

// ── 進階設定 ──
function toggleAdvanced() {
    const settings = document.getElementById('advanced-settings');
    const arrow = document.getElementById('advanced-arrow');
    settings.classList.toggle('hidden');
    arrow.classList.toggle('rotated');
}

// ── 進度動畫 ──
function showProgress(step, percent) {
    const progressSection = document.getElementById('progress-section');
    progressSection.classList.remove('hidden');

    const steps = ['step-download', 'step-analyze', 'step-generate'];
    steps.forEach((id, idx) => {
        const el = document.getElementById(id);
        el.classList.remove('active', 'done');
        if (idx < step) el.classList.add('done');
        if (idx === step) el.classList.add('active');
    });

    document.getElementById('progress-fill').style.width = `${percent}%`;
}

function hideProgress() {
    document.getElementById('progress-section').classList.add('hidden');
}

// ── 核心：開始轉譜 ──
async function startTranscribe() {
    const urlInput = document.getElementById('youtube-url');
    const url = urlInput.value.trim();

    if (!url) {
        showToast('請輸入 YouTube 連結');
        urlInput.focus();
        return;
    }

    if (!url.includes('youtube.com') && !url.includes('youtu.be')) {
        showToast('請輸入有效的 YouTube 連結');
        return;
    }

    const btn = document.getElementById('transcribe-btn');
    const btnText = btn.querySelector('.btn-text');
    const btnLoading = btn.querySelector('.btn-loading');

    btn.disabled = true;
    btnText.classList.add('hidden');
    btnLoading.classList.remove('hidden');

    const resultSection = document.getElementById('result-section');
    resultSection.classList.add('hidden');

    try {
        showProgress(0, 10);
        await delay(500);
        showProgress(0, 30);

        const keyOffset = parseInt(document.getElementById('key-select').value) || 0;

        showProgress(1, 50);

        const response = await fetch(`${API_BASE}/api/transcribe`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                youtube_url: url,
                output_type: currentType,
                key_offset: keyOffset,
            }),
        });

        showProgress(2, 80);

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '轉譜失敗');
        }

        const data = await response.json();
        showProgress(2, 100);

        await delay(400);
        hideProgress();

        displayResult(data);
        currentResult = data;
        showToast('🎉 轉譜完成！');
    } catch (error) {
        hideProgress();

        // 任何錯誤都 fallback 到演示模式，提供更好的體驗
        showDemoResult(url);
        if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
            showToast('⚠️ 後端未啟動，顯示演示模式');
        } else {
            showToast(`⚠️ ${error.message}（已顯示演示模式）`);
        }
    } finally {
        btn.disabled = false;
        btnText.classList.remove('hidden');
        btnLoading.classList.add('hidden');
    }
}

// ── 顯示結果 ──
function displayResult(data) {
    const section = document.getElementById('result-section');
    section.classList.remove('hidden');

    document.getElementById('result-title').textContent = data.title || '未知歌曲';
    document.getElementById('result-tempo').textContent = `♩ = ${data.tempo || 120}`;
    document.getElementById('result-key').textContent = `${data.key || 'C'} 大調`;

    const typeLabels = {
        chord_sheet: '🎤 彈唱簡譜',
        fingerstyle_tab: '🎸 指彈六線譜',
        piano_sheet: '🎹 鋼琴簡譜',
    };
    document.getElementById('result-type').textContent = typeLabels[data.output_type] || '';

    document.getElementById('sheet-content').textContent = data.content;

    const noteEl = document.getElementById('result-note');
    if (data.midi_note) {
        noteEl.textContent = data.midi_note;
        noteEl.classList.remove('hidden');
    } else {
        noteEl.classList.add('hidden');
    }

    section.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── 演示模式結果 ──
function showDemoResult(url) {
    const demoChordSheet = `速度: ♩ = 120
調號: C 大調

 [C]          [Am]         [F]          [G]  
  1   3   5    6   1·  5    4   3   2    5   -   -

 [C]          [G]          [Am]         [F]  
  1   1   2    5,  7,  2    6,  1   3    4   3   1

 [F]          [G]          [C]               
  4   4   5    7   2·  1    1   -   -    -   -   -

※ 這是演示模式的範例簡譜。
   啟動後端服務後，將從 YouTube 音訊即時產生真實樂譜。`;

    const demoFingerstyleTab = `速度: ♩ = 120
Tuning: Standard (EADGBE)

e| -  0  -  1  -  0  -  -  3  -  1  -  0  -  -  -|
B| 1  -  1  -  3  -  1  0  -  0  -  3  -  1  0  -|
G| -  0  -  -  -  0  -  -  -  0  -  -  -  0  -  0|
D| 2  -  2  -  -  -  2  -  0  -  0  -  -  -  2  -|
A| 3  -  -  0  -  -  -  -  -  -  -  0  -  -  3  -|
E| -  -  -  -  -  -  -  3  -  -  -  -  3  -  -  -|

※ 這是演示模式的範例指彈譜。`;

    const demoPianoSheet = `速度: ♩ = 120
調號: C 大調

右手（旋律）：
  1   3   5   1·  6   5   3   1   4   3   2   5   1   -   -   -

左手（伴奏）：
  1,  5,  3,  1,  4,  1,  5,  7,  4,  1,  5,  2,  1,  -   -   -

※ 這是演示模式的範例鋼琴簡譜。`;

    const demoSheets = {
        chord_sheet: demoChordSheet,
        fingerstyle_tab: demoFingerstyleTab,
        piano_sheet: demoPianoSheet,
    };

    const demoData = {
        id: 'demo-' + Date.now(),
        youtube_url: url,
        title: '🎵 演示範例（後端未啟動）',
        output_type: currentType,
        content: demoSheets[currentType] || demoChordSheet,
        tempo: 120,
        key: 'C',
        created_at: new Date().toISOString(),
        midi_note: '💡 提示：請先啟動後端服務 (cd backend && uv run main.py)，即可進行真實的 YouTube 轉譜。',
    };

    displayResult(demoData);
    currentResult = demoData;

    saveToLocalHistory(demoData);
}

// ── 複製到剪貼簿 ──
async function copyToClipboard() {
    const content = document.getElementById('sheet-content').textContent;
    try {
        await navigator.clipboard.writeText(content);
        showToast('📋 已複製到剪貼簿');
    } catch {
        const ta = document.createElement('textarea');
        ta.value = content;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        showToast('📋 已複製到剪貼簿');
    }
}

// ── 收藏功能 ──
async function toggleFavorite() {
    if (!currentResult) return;

    const favIcon = document.getElementById('fav-icon');
    const favorites = getLocalFavorites();
    const exists = favorites.find(f => f.id === currentResult.id);

    if (exists) {
        const updated = favorites.filter(f => f.id !== currentResult.id);
        localStorage.setItem('tab-finder-favorites', JSON.stringify(updated));
        favIcon.textContent = '☆';
        showToast('已取消收藏');
    } else {
        favorites.unshift(currentResult);
        localStorage.setItem('tab-finder-favorites', JSON.stringify(favorites));
        favIcon.textContent = '⭐';
        showToast('⭐ 已加入收藏');
    }

    // 嘗試同步到後端（如果可用）
    if (!IS_GITHUB_PAGES) {
        try {
            if (!exists) {
                await fetch(`${API_BASE}/api/favorites`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ record_id: currentResult.id }),
                });
            } else {
                await fetch(`${API_BASE}/api/favorites/${currentResult.id}`, {
                    method: 'DELETE',
                });
            }
        } catch {
            // 離線模式，只用本地儲存
        }
    }
}

// ── 本地儲存 ──
function saveToLocalHistory(record) {
    const history = JSON.parse(localStorage.getItem('tab-finder-history') || '[]');
    history.unshift(record);
    if (history.length > 50) history.length = 50;
    localStorage.setItem('tab-finder-history', JSON.stringify(history));
}

function getLocalFavorites() {
    return JSON.parse(localStorage.getItem('tab-finder-favorites') || '[]');
}

// ── 載入歷史記錄 ──
async function loadHistory() {
    let records = [];

    if (IS_GITHUB_PAGES) {
        // GitHub Pages 模式：使用靜態資料
        records = allSheets;
    } else {
        try {
            const res = await fetch(`${API_BASE}/api/history`);
            if (res.ok) records = await res.json();
        } catch {
            records = JSON.parse(localStorage.getItem('tab-finder-history') || '[]');
        }
    }

    renderRecordList('history-list', records, false);
}

// ── 載入收藏 ──
async function loadFavorites() {
    let records = [];

    if (IS_GITHUB_PAGES) {
        records = getLocalFavorites();
    } else {
        try {
            const res = await fetch(`${API_BASE}/api/favorites`);
            if (res.ok) records = await res.json();
        } catch {
            records = getLocalFavorites();
        }
    }

    renderRecordList('favorites-list', records, true);
}

// ── 渲染記錄列表 ──
function renderRecordList(containerId, records, isFavorites) {
    const container = document.getElementById(containerId);

    if (!records || records.length === 0) {
        container.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon">${isFavorites ? '⭐' : '🎵'}</span>
        <p>${isFavorites ? '還沒有收藏' : '還沒有轉譜記錄'}</p>
        <p class="empty-hint">${isFavorites ? '點擊樂譜旁的 ☆ 即可收藏' : '試試貼上一個 YouTube 連結吧！'}</p>
      </div>`;
        return;
    }

    const typeLabels = {
        chord_sheet: '🎤 簡譜',
        fingerstyle_tab: '🎸 指彈譜',
        piano_sheet: '🎹 鋼琴譜',
    };

    container.innerHTML = records.map(record => `
    <div class="record-card" onclick='viewRecord(${JSON.stringify(record).replace(/'/g, "&#39;")})'>
      <div class="record-card-header">
        <span class="record-card-title">${escapeHtml(record.title || '未知歌曲')}</span>
        <span class="record-card-date">${formatDate(record.created_at)}</span>
      </div>
      <div class="record-card-meta">
        <span class="record-type-tag">${typeLabels[record.output_type] || '樂譜'}</span>
        <span class="meta-tag">♩ = ${record.tempo || 120}</span>
      </div>
    </div>
  `).join('');
}

// ── 檢視記錄 ──
function viewRecord(record) {
    currentResult = record;
    displayResult(record);
    switchTab('transcribe');
}

// ── 工具函數 ──
function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.remove('hidden');
    toast.classList.add('show');

    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.classList.add('hidden'), 300);
    }, 2500);
}

function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatDate(isoStr) {
    if (!isoStr) return '';
    const d = new Date(isoStr);
    const month = (d.getMonth() + 1).toString().padStart(2, '0');
    const day = d.getDate().toString().padStart(2, '0');
    const hour = d.getHours().toString().padStart(2, '0');
    const min = d.getMinutes().toString().padStart(2, '0');
    return `${month}/${day} ${hour}:${min}`;
}

// ── PWA Service Worker 註冊 ──
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then(reg => console.log('SW 已註冊:', reg.scope))
            .catch(err => console.log('SW 註冊失敗:', err));
    });
}
