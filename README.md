# Vaud-AirBnB: Airbnb Data Engineering & Analytics Pipeline

An end-to-end data engineering and analytics pipeline — taking Inside Airbnb data for the Vaud region of Switzerland from raw ingestion all the way to a live cloud analytics dashboard, using Python, PostgreSQL, Supabase, and Streamlit.


🔗 **[Live Dashboard](https://airbnb-datascience-project.streamlit.app)** &nbsp;|&nbsp; 📦 **Stack:** Python · PostgreSQL · Supabase · Streamlit · Docker · HuggingFace Transformers

<img width="1919" height="968" alt="image" src="https://github.com/user-attachments/assets/089e180b-fd4c-42cc-a78e-510d2e5004e4" />

---

## 📌 Project Overview

This project builds a full analytics pipeline on real Inside Airbnb data for Vaud, Switzerland (5,249 listings, 134,598 reviews, ~1.9M calendar rows). The pipeline handles everything from raw ingestion through star-schema modeling, statistical hypothesis testing, multilingual sentiment analysis, and a live Streamlit dashboard.

**Key business metrics tracked:**
- Price drivers by neighbourhood, room type, and host status
- Guest sentiment across English, French, German, and Italian reviews
- Host concentration and supply-side market structure
- Seasonal availability and demand trends

**Key findings:**
- Neighbourhood is the strongest driver of price (epsilon-squared = 0.18)
- Room type is the most actionable lever a host controls (rank-biserial = 0.55)
- Superhost status is statistically significant but practically negligible for price (rank-biserial = 0.07)
- A multilingual BERT model was run on all 134,591 reviews for sentiment scoring

---

## 🏗️ Architecture

Raw Data (CSV / CSV.GZ / GeoJSON)
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;▼
Python Ingestion (src/ingestion/ingest.py)
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;▼
PostgreSQL (Docker, local)
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;▼
Validation (profile.py, quality.py)
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;▼
Transformation (transform.py → *_clean tables)
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;▼
Star Schema Modeling (dim_* / fact_* + listings_master)
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;▼
Supabase (cloud Postgres, migrated via migrate_to_supabase.py)
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;├──► Sentiment Analysis (Google Colab, T4 GPU) ──► review_sentiment table
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;▼
Streamlit Dashboard (Deployed on Streamlit Community Cloud)

This is an **ELT** pipeline, not ETL — raw data lands in Postgres almost untouched, with all cleaning and standardization happening afterward in `transform.py`. Raw tables are kept alongside their `*_clean` counterparts for a full audit trail.

---

## 🛠️ Tech Stack

| Tool | Purpose |
|------|---------|
| **Python** | Ingestion, validation, transformation, modeling scripts |
| **PostgreSQL** | Local relational database (via Docker) for raw and transformed data |
| **Docker** | Containerized local PostgreSQL environment |
| **Supabase** | Cloud-hosted PostgreSQL — powers the live dashboard |
| **SQLAlchemy** | Database connection layer (`src/utils/db.py`) |
| **pandas / numpy / scipy / statsmodels** | Data transformation, EDA, and statistical hypothesis testing |
| **HuggingFace Transformers** | `nlptown/bert-base-multilingual-uncased-sentiment` for sentiment scoring |
| **Google Colab (T4 GPU)** | GPU-accelerated sentiment inference on 134,591 reviews |
| **Streamlit + Plotly** | Interactive analytics dashboard |
| **Folium** | Geographic/spatial visualization in EDA |

---

## 📁 Project Structure

```
Vaud-AnB/
│
├── src/
│   ├── ingestion/           # ingest.py — raw file → Postgres
│   ├── validation/          # profile.py, quality.py
│   ├── transformation/      # transform.py, build_master.py
│   ├── modeling/            # dim_*.py, fact_*.py — star schema builders
│   └── utils/                # config.py, db.py
├── data/                     # Raw Inside Airbnb source files
├── logs/                     # Per-module pipeline logs
├── EDA_notebook/
│   └── eda.ipynb             # Exploratory data analysis
├── Stats_notebook/
│   └── stats.ipynb           # H1–H5 hypothesis testing
├── NLP_notebook/
│   └── NLP_sentiment.ipynb   # Sentiment analysis (built for Colab GPU)
├── notebooks/                 # Supplementary/exploratory notebooks
├── .streamlit/
│   └── config.toml           # Streamlit app configuration
├── check_schema.py           # Schema validation utility
├── migrate_to_supabase.py    # Local Postgres → Supabase migration
├── docker-compose.yml        # Local PostgreSQL setup
├── Streamlit_app.py          # Dashboard entry point
├── requirements.txt
└── .env                       # Environment variables (gitignored)
```

---

## 🗃️ Star Schema

Three dimension tables and two fact tables, sharing common dimensions for consistent cross-analysis:

| Table | Type | Grain |
|-------|------|-------|
| `dim_listing` | Dimension | One row per listing |
| `dim_neighbourhood` | Dimension | One row per neighbourhood |
| `dim_date` | Dimension | One row per date (2010–2027) |
| `fact_calendar` | Fact | One row per listing per day (availability, min/max nights) |
| `fact_reviews` | Fact | One row per review |

Two fact tables were used because calendar and review data represent different business events at different granularities, while sharing the same dimensions.

---

## 📊 Statistical Findings

Five formally tested hypotheses (H1–H5), using non-parametric tests throughout since price data consistently failed normality (D'Agostino's K²) and equal-variance (Levene's) checks:

| Hypothesis | Test | Effect Size | Result |
|---|---|---|---|
| H1: Room type vs. price | Mann-Whitney U | r = 0.55 (large) | Entire-home listings command a significant premium |
| H2: Superhost vs. review score | Mann-Whitney U | r = 0.07 (negligible) | Statistically real, practically trivial |
| H3: Review count vs. price | Mann-Whitney U | r = 0.15 (small) | Weak, counterintuitive relationship |
| H4: Neighbourhood vs. price | Kruskal-Wallis | ε² = 0.18 (large) | Strongest price driver tested |
| H5: Weekend vs. weekday pricing | — | — | Not testable — no date-varying price field in source data |

---

## 🧠 Sentiment Analysis

- **Model:** `nlptown/bert-base-multilingual-uncased-sentiment` — chosen for coverage across English, French, German, and Italian reviews
- **Scale:** 134,591 reviews processed
- **Compute:** Google Colab (T4 GPU) — local PyTorch installation was impractically slow for this workload
- **Output:** 1–5 star sentiment prediction rescaled to -1..1, written to a `review_sentiment` table in Supabase, joinable to `listings_master` for dashboard use

---

## 🚀 Getting Started

### Prerequisites
- Docker & Docker Compose
- Python 3.13
- A Supabase account (for cloud/dashboard connectivity)

### 1. Clone the repo
```bash
git clone https://github.com/yuwaniyash/Airbnb-DataScience-Project.git
cd Airbnb-DataScience-Project
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up environment variables
Create a `.env` file in the root directory:
```env
DATABASE_URL=postgresql://vaud_user:<password>@localhost:5432/vaud_airbnb
SUPABASE_DATABASE_URL=<your Supabase connection string>
```

### 4. Start local PostgreSQL
```bash
docker-compose up -d
```

### 5. Run the pipeline
```bash
python -m src.ingestion.ingest
python -m src.validation.profile
python -m src.validation.quality
python -m src.transformation.transform
python -m src.transformation.build_master
python -m src.modeling.dim_date
python -m src.modeling.dim_neighbourhood
python -m src.modeling.dim_listing
python -m src.modeling.fact_calendar
python -m src.modeling.fact_reviews
```

### 6. Migrate to Supabase
```bash
python migrate_to_supabase.py
```

### 7. Run the dashboard locally
```bash
streamlit run Streamlit_app.py
```

---

## 📈 Dashboard Features

- **Market Overview** — Listing counts, price distributions, room type breakdown
- **Geographic Analysis** — Neighbourhood-level pricing and listing density
- **Statistical Findings** — H1–H5 results with effect sizes
- **Sentiment Insights** — Review sentiment by neighbourhood/time, cross-referenced with ratings
- **Interactive Filters** — Region, neighbourhood, room type, host status, price, rating

---

## ⚠️ Known Data Limitations

- ~33% of listings have no recorded price (source data gap — flagged via `has_price`, not imputed)
- `fact_calendar` has no price field — only availability, so seasonal price fluctuation can't be directly analyzed
- Single snapshot in time (scraped 23 May 2026) — no historical change tracking
- ~47.6% of listings show zero estimated occupancy in the trailing 365 days




---

## 🤖 AI Usage Disclosure

This project made use of Claude (Anthropic) and ChatGPT as technical assistants during development — for pipeline debugging, statistical methodology guidance, sentiment model selection, and report review. Full disclosure, including key prompts and where AI assistance was deliberately *not* used.

---

## 👩‍💻 About

Built by **K. Yuwani Yasmada** — IT undergraduate specializing in Data Science at SLIIT (Sri Lanka Institute of Information Technology).

📧 yuwi.y2003@gmail.com
🔗 [GitHub Repo](https://github.com/yuwaniyash/Airbnb-DataScience-Project)

