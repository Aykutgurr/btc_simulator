# BTC Futures Simulator

Bu repo iki farklı arayüzle (frontend) çalıştırılabilir:

- **Masaüstü UI (PyQt5)**: `main.py` üzerinden çalışır.
- **Web UI (React/Vite)**: `btc-simulator-web-frontend/` + **FastAPI backend** `web_api.py` ile çalışır.

---

## Masaüstü UI (PyQt5) — Çalıştırma

### 1) Python ortamı oluştur

PowerShell:

```powershell
cd "c:\Users\aykut\OneDrive\Masaüstü\btc_simulator"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2) Uygulamayı başlat

```powershell
python main.py
```

Notlar:
- Veri seçimi / tarih aralığı için açılışta `startup_dialog.py` gelir.
- Bot logları UI içinde **Botlar & İstatistikler** sekmesinde görünür.

---

## Web UI (React/Vite) + Backend (FastAPI) — Birlikte Çalıştırma

### 1) Backend (FastAPI) — `web_api.py`

Yeni bir terminal aç:

```powershell
cd "c:\Users\aykut\OneDrive\Masaüstü\btc_simulator"
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python web_api.py
```

Varsayılan:
- REST API: `http://localhost:8000/api/...`
- WebSocket: `ws://localhost:8000/ws`

LLM Bot Builder (Ollama) kullanıyorsanız varsayılan model:
- `qwen2.5:7b-instruct` (backend env ile değiştirilebilir: `LLM_MODEL`)

### 2) Frontend (React/Vite) — `btc-simulator-web-frontend/`

Yeni bir terminal aç:

```powershell
cd "c:\Users\aykut\OneDrive\Masaüstü\btc_simulator\btc-simulator-web-frontend"
npm install
npm run dev
```

Frontend varsayılan olarak **mock mode** ile açılabilir. Backend’e bağlamak için env ayarları:

`btc-simulator-web-frontend/.env.local` (örnek):

```bash
VITE_MOCK_MODE=false
VITE_API_BASE_URL=/api
VITE_WS_URL=ws://localhost:8000/ws
```

Sonra `npm run dev` ile yeniden başlat.

---

## Sık Karşılaşılan Sorunlar

### `pandas_ta` / indikatörler yok
- `requirements.txt` içindeki `pandas-ta` kurulu olmalı:

```powershell
pip install pandas-ta
```

### Port çakışması (8000)
- `web_api.py` varsayılan portu **8000**. Gerekirse dosyada `uvicorn.run(..., port=XXXX)` değiştir.

---

## Proje Yapısı (kısa)

```
btc_simulator/
├── main.py, web_api.py          # Giriş noktaları (masaüstü + web API)
├── data_engine.py, trading_engine.py, ui_components.py, drawing_tools.py
├── startup_dialog.py, sandbox_runner.py
├── data/                        # btc_ohlcv.csv (varsayılan veri)
├── bots/                        # Strateji botları + generated/
├── bot_sdk/                     # Bot yardımcıları
├── llm/                         # Ollama bot üretimi
├── models/                      # Eğitilmiş ML modelleri
├── scripts/                     # train_*.py eğitim scriptleri
├── logs/                        # Bot/işlem CSV exportları (gitignore)
├── docs/                        # WEB_API.md, tez metni, şablonlar
├── tools/presentation/          # Sunum üretici (opsiyonel)
└── btc-simulator-web-frontend/    # React/Vite web arayüzü
```

Web API dokümantasyonu: [docs/WEB_API.md](docs/WEB_API.md)

