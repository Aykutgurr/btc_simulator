# BTC Simulator — Web Frontend

Bu klasör `btc_simulator` projesi için React + TypeScript tabanlı web arayüzüdür.

## Çalıştırma

```bash
npm install
npm run dev
```

Varsayılan davranış:
- **Development modda** (`npm run dev`) frontend varsayılan olarak **mock mode** ile çalışır (backend olmadan UI açılır).
- Production build için:

```bash
npm run build
npm run preview
```

## Ortam Değişkenleri

`.env` dosyası (veya sistem env) ile ayarlayabilirsiniz:

- `VITE_API_BASE_URL`: API base url (default: `/api`)
- `VITE_WS_URL`: WebSocket url (default: `ws://localhost:8000/ws`)
- `VITE_MOCK_MODE`: `true|false`
  - `true`: her zaman mock API/WS
  - `false`: gerçek backend’e istek atar

## Backend entegrasyonu (özet)

Frontend şu sözleşmeye göre istek atar:
- REST: `/api/session`, `/api/market/state`, `/api/trade/state`, `/api/bots`, `/api/logs`, vb.
- WS: `/ws` üzerinden `candle`, `stats`, `tradeClosed`, `tfClose`, `log` eventleri

Backend henüz yoksa mock mode ile UI’yı test edebilirsiniz.

## LLM Bot Builder (Ollama)

UI icinden yeni strateji botu uretip sandbox icinde test edebilirsiniz.

- **Gereksinim**: Ollama calisiyor olmali (varsayilan `http://localhost:11434`)
- **Model**: `qwen2.5:7b-instruct`

### Adimlar
1) Backend: `python ..\\web_api.py`
2) Ollama:

```bash
ollama pull qwen2.5:7b-instruct
ollama serve
```

3) UI: **Botlar & İstatistikler** sekmesi > **Yeni Bot Üret**
   - Bot adi + timeframe + strateji tarifi
   - **Üret** sonra **Test Et**

