/**
 * Music Tab Finder - 前端互動邏輯
 * 處理 YouTube 轉譜請求、歷史/收藏管理與 PWA 功能。
 */

// ── 設定 ──
const API_BASE = 'http://localhost:8000';
let currentType = 'chord_sheet';
let currentResult = null;

// ── 頁簽切換 ──
function switchTab(tabName) {
    // 更新按鈕狀態
    document.querySelectorAll('.nav-tab').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    // 更新內容區
    document.querySelectorAll('.tab-content').forEach(section => {
        section.classList.toggle('active', section.id === `tab-${tabName}`);
    });

    // 載入列表
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

    // 簡單的 YouTube URL 驗證
    if (!url.includes('youtube.com') && !url.includes('youtu.be')) {
        showToast('請輸入有效的 YouTube 連結');
        return;
    }

    const btn = document.getElementById('transcribe-btn');
    const btnText = btn.querySelector('.btn-text');
    const btnLoading = btn.querySelector('.btn-loading');

    // 進入載入狀態
    btn.disabled = true;
    btnText.classList.add('hidden');
    btnLoading.classList.remove('hidden');

    const resultSection = document.getElementById('result-section');
    resultSection.classList.add('hidden');

    try {
        // 模擬進度
        showProgress(0, 10);
        await delay(500);
        showProgress(0, 30);

        const keyOffset = parseInt(document.getElementById('key-select').value) || 0;

        // 發送 API 請求
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

        // 顯示結果
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

    // 滾動到結果
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

    // 存入 localStorage 歷史
    saveToLocalHistory(demoData);
}

// ── 複製到剪貼簿 ──
async function copyToClipboard() {
    const content = document.getElementById('sheet-content').textContent;
    try {
        await navigator.clipboard.writeText(content);
        showToast('📋 已複製到剪貼簿');
    } catch {
        // 備用方案
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
        // 取消收藏
        const updated = favorites.filter(f => f.id !== currentResult.id);
        localStorage.setItem('tab-finder-favorites', JSON.stringify(updated));
        favIcon.textContent = '☆';
        showToast('已取消收藏');
    } else {
        // 加入收藏
        favorites.unshift(currentResult);
        localStorage.setItem('tab-finder-favorites', JSON.stringify(favorites));
        favIcon.textContent = '⭐';
        showToast('⭐ 已加入收藏');
    }

    // 嘗試同步到後端（如果可用）
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

    try {
        const res = await fetch(`${API_BASE}/api/history`);
        if (res.ok) records = await res.json();
    } catch {
        // 使用本地歷史
        records = JSON.parse(localStorage.getItem('tab-finder-history') || '[]');
    }

    renderRecordList('history-list', records, false);
}

// ── 載入收藏 ──
async function loadFavorites() {
    let records = [];

    try {
        const res = await fetch(`${API_BASE}/api/favorites`);
        if (res.ok) records = await res.json();
    } catch {
        records = getLocalFavorites();
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

// ── Enter 快捷鍵 ──
document.addEventListener('DOMContentLoaded', () => {
    const urlInput = document.getElementById('youtube-url');
    urlInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            startTranscribe();
        }
    });
});
