## Web API (FastAPI) — btc_simulator

Bu repo icindeki `btc-simulator-web-frontend/` web arayuzunun gercek veriyle calismasi icin minimal bir backend sunucusu.

### Calistirma

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python web_api.py
```

- Varsayilan: `http://localhost:8000`
- REST: `http://localhost:8000/api/...`
- WebSocket: `ws://localhost:8000/ws`

### Frontend baglama (Vite dev)

`btc-simulator-web-frontend/` klasorunde:

```bash
set VITE_MOCK_MODE=false
set VITE_API_BASE_URL=http://localhost:8000/api
set VITE_WS_URL=ws://localhost:8000/ws
npm run dev
```

### LLM Bot Builder (Ollama)

Bu proje web UI icinden yeni strateji botu uretebilir ve sandbox icinde test edebilir.

#### Ollama kurulum / calistirma

```bash
ollama pull llama3.2:3b
ollama serve
```

Backend varsayilanlari:
- `LLM_BASE_URL=http://localhost:11434`
- `LLM_MODEL=llama3.2:3b`

#### UI Akisi
- Web UI > **Botlar & Istatistikler** > **Yeni Bot Uret**
- Bot adi + timeframe + strateji tarifi gir
- **Uret** > sonra **Test Et**

Not: Uretimde hata olursa backend otomatik olarak 1-2 kez \"repair\" denemesi yapar (hata mesajini modele geri verir).

