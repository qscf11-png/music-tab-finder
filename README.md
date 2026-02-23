# 🎵 Music Tab Finder - AI 音樂轉譜助手

從 YouTube 連結自動產生吉他簡譜、指彈譜與鋼琴譜。

## 功能特色

- 🎤 **彈唱簡譜**：和弦 + 數字簡譜，適合吉他彈唱
- 🎸 **指彈六線譜**：完整 Fingerstyle Tab，含低音與旋律
- 🎹 **鋼琴簡譜**：雙手分離的數字簡譜
- 📱 **手機支援**：PWA + RWD 響應式設計，可安裝到手機桌面
- ⭐ **收藏功能**：儲存喜愛的樂譜，隨時回顧

## 快速開始

### 一鍵啟動

```bat
雙擊 start.bat
```

### 手動啟動

```powershell
cd backend
uv run main.py
```

啟動後：

- 電腦瀏覽器開啟 <http://localhost:8000>
- 手機在同一 WiFi 下開啟 http://<你的電腦IP>:8000

## 使用方式

1. 貼上 YouTube 連結
2. 選擇樂譜類型（彈唱簡譜 / 指彈譜 / 鋼琴譜）
3. 點擊「開始轉譜」
4. 檢視或收藏產出的樂譜

## 技術架構

- **後端**：Python + FastAPI + yt-dlp + pretty-midi
- **前端**：純 HTML/CSS/JS + PWA
- **環境**：uv 管理 Python 虛擬環境
