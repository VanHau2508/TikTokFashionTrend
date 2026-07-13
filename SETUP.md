# TikTokFashionTrend - Huong dan cai dat

Sau khi `git clone`, ban KHONG co san cac package (node_modules, thu vien Python)
va cac file model AI. Lam theo cac buoc duoi de chay duoc he thong.

## 1. Backend (Python / FastAPI)

```bash
# Tao moi truong ao
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Cai package
pip install -r requirements.txt

# Cai trinh duyet cho Playwright (crawler TikTok)
playwright install
```

## 2. Frontend (React / Vite)

```bash
cd frontend
npm install
npm run dev
```

## 3. Bien moi truong

Tao file `.env` (dua theo `.env.example` neu co) chua thong tin ket noi
PostgreSQL, khoa bi mat JWT, v.v. File `.env` va `cookies.json` KHONG duoc
day len repo vi ly do bao mat.

## 4. Model AI

Cac file trong so (`.pt`, `.pth`, ...) khong nam trong repo. Xem
`ai/models/README.md` de biet cach tai hoac huan luyen lai model.

## 5. Co so du lieu

Khoi tao PostgreSQL bang cac file schema trong thu muc `database/`.
