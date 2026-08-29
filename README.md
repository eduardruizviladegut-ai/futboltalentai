# ⚽🤖 Football Talent AI — v1 (MVP)

Backend de la plataforma de scouting inteligente. Esta v1 cubre el
primer tramo del roadmap del proyecto:

```
Jugador → Estadísticas → Atributos 0-100 → Media → (similitud y explicación IA: fase 2)
```

## Qué incluye esta v1

- **Base de datos PostgreSQL** con esquema completo (`db/schema.sql`):
  jugadores, equipos, competiciones, stats crudas, atributos por
  posición, historial mensual, Player DNA, similitud, Hidden Gems.
- **Backend FastAPI** (`app/`) con endpoints:
  - `GET /players` — listado con filtros (nombre, posición, equipo)
  - `GET /players/{id}/card` — Player Card completa (media + atributos)
  - `GET /players/{id}/evolution` — historial mensual de la media
- **Script de ingesta** (`ingestion/`) que descarga stats de la
  **Premier League** desde la API interna de Sofascore y las guarda
  como snapshot mensual.
- **Cálculo de atributos** (`app/services/attributes.py`): fórmulas
  configurables por posición, guardadas en base de datos, no en código.

## ⚠️ Nota importante sobre la fuente de datos

Sofascore no ofrece API pública ni licencia de uso comercial. Esta v1
usa su API interna con fines de validación/MVP, aceptando que:
- El acceso puede romperse si Sofascore cambia su protección.
- No es apta para producto monetizado sin migrar a una fuente con
  licencia (Sportmonks, API-Football, etc.) — ver `data_sources.is_commercial_ok`
  en el esquema, que deja esto explícito en el propio dato.

## Estructura del repo

```
football-talent-ai/
├── app/
│   ├── main.py              # entrypoint FastAPI
│   ├── config.py            # variables de entorno
│   ├── database.py          # conexión SQLAlchemy
│   ├── models.py            # modelos ORM
│   ├── schemas.py           # esquemas Pydantic de respuesta
│   ├── routers/
│   │   └── players.py       # endpoints de jugadores
│   └── services/
│       └── attributes.py    # cálculo de atributos 0-100
├── ingestion/
│   ├── sofascore_client.py  # cliente de la API interna de Sofascore
│   └── ingest_premier_league.py  # script de ingesta piloto
├── db/
│   ├── schema.sql           # DDL completo
│   └── seed_formulas.sql    # fórmulas iniciales de atributos por posición
├── requirements.txt
├── render.yaml               # config de despliegue en Render
└── .env.example
```

---

## 🚀 Despliegue paso a paso (GitHub + Render)

### 1. Subir el proyecto a GitHub

```bash
cd football-talent-ai
git init
git add .
git commit -m "v1 MVP: backend + ingesta Premier League desde Sofascore"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/football-talent-ai.git
git push -u origin main
```

(Si no tienes el repo creado aún en GitHub: crea uno nuevo, vacío, sin
README ni .gitignore — ya los trae este proyecto — y copia la URL que
te da GitHub para el paso `git remote add origin`.)

### 2. Crear los servicios en Render

Render puede leer `render.yaml` automáticamente:

1. Entra a [render.com](https://render.com) → **New** → **Blueprint**.
2. Conecta tu cuenta de GitHub y selecciona el repo `football-talent-ai`.
3. Render detecta `render.yaml` y propone crear:
   - Un **Web Service** (`football-talent-ai-api`) — el backend FastAPI.
   - Una **base de datos PostgreSQL** (`football-talent-ai-db`).
4. Confirma. Render construye e instala `requirements.txt`, y conecta
   automáticamente `DATABASE_URL` del servicio web a la base de datos
   (no hace falta que copies ninguna cadena de conexión a mano).
5. Espera a que el estado del servicio web pase a **Live**.

### 3. Cargar el esquema en la base de datos

Con la base de datos ya creada en Render, necesitas ejecutar el DDL una
vez. Desde tu máquina, con `psql` instalado:

```bash
# La cadena de conexión externa la ves en Render → tu base de datos → "External Database URL"
psql "TU_EXTERNAL_DATABASE_URL" -f db/schema.sql
psql "TU_EXTERNAL_DATABASE_URL" -f db/seed_formulas.sql
```

### 4. Correr la ingesta piloto (Premier League)

Puedes correrla en local apuntando a la base de datos de Render:

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export DATABASE_URL="TU_EXTERNAL_DATABASE_URL"        # Windows: set DATABASE_URL=...
python -m ingestion.ingest_premier_league
```

Esto puede tardar varios minutos (hay ~20 equipos con ~25 jugadores
cada uno, y el cliente respeta una pausa entre peticiones para no
saturar Sofascore).

### 5. Comprobar que la API responde

```bash
curl https://TU-SERVICIO.onrender.com/health
curl https://TU-SERVICIO.onrender.com/players?limit=5
```

La documentación interactiva (Swagger) queda disponible en:
`https://TU-SERVICIO.onrender.com/docs`

---

## Desarrollo local (opcional, sin Render)

```bash
# Levantar PostgreSQL local (o usar uno ya instalado)
createdb football_talent_ai
psql football_talent_ai -f db/schema.sql
psql football_talent_ai -f db/seed_formulas.sql

cp .env.example .env
pip install -r requirements.txt

uvicorn app.main:app --reload
# API en http://localhost:8000/docs
```

---

## Próximos pasos (fuera de esta v1)

Según el roadmap del documento de producto (`Football_Talent_AI_Proyecto.md`):

- Calcular `player_monthly_rating` a partir de los snapshots ingeridos
  (por ahora la ingesta llena `player_stats_snapshot`; falta el job
  que aplique `app/services/attributes.py` y guarde el resultado mensual).
- Endpoint de comparador de jugadores.
- Sistema de similitud (`player_similarity`) — requiere vectorizar
  `player_profile_vector` y elegir un modelo (ej. cosine similarity
  con scikit-learn, como indica la sección 15 del documento).
- Integración con LLM para las explicaciones de IA (`ai_explanation`).
- Frontend (Next.js) que consuma esta API.
