

import os
import re
import pathlib
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine, text, bindparam
from dotenv import load_dotenv

# ----------------------------------------------------------------------
# Theme (auto-written to .streamlit/config.toml on startup)
# ----------------------------------------------------------------------
# Streamlit only reads theme colors from .streamlit/config.toml, and only
# at process startup — there's no in-script API for it. So we keep the
# theme definition here as the single source of truth, and write the file
# out ourselves so you never have to manage it by hand.
_THEME_TOML = """[theme]
base = "dark"
primaryColor = "#6366f1"
backgroundColor = "#0e1117"
secondaryBackgroundColor = "#171a24"
textColor = "#e5e7eb"
font = "sans serif"
"""

_config_dir = pathlib.Path(__file__).parent / ".streamlit"
_config_dir.mkdir(exist_ok=True)
_config_path = _config_dir / "config.toml"
if not _config_path.exists() or _config_path.read_text() != _THEME_TOML:
    _config_path.write_text(_THEME_TOML)
    # Config is only picked up on process start, so if we just wrote it
    # for the first time, this run is still using Streamlit's defaults.
    _theme_just_created = True
else:
    _theme_just_created = False

# ----------------------------------------------------------------------
# Setup
# ----------------------------------------------------------------------
st.set_page_config(page_title="Vaud Airbnb Dashboard", layout="wide")

load_dotenv()

if _theme_just_created:
    st.warning(
        "Theme file was just created — restart the app (Ctrl+C, then `streamlit run app.py` again) "
        "to see the dark/indigo theme applied natively."
    )

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body {
    font-family: 'Inter', -apple-system, sans-serif;
}

/* Icons use a ligature font (e.g. keyboard_arrow_down renders as an arrow
   glyph) — restore their own font so the global override above doesn't
   turn them into literal text like the expander arrows did. */
[data-testid="stIconMaterial"],
span[class*="material-symbols"],
span[class*="material-icons"] {
    font-family: 'Material Symbols Rounded', 'Material Icons' !important;
}

:root {
    --accent: #6366f1;
    --accent-soft: rgba(99, 102, 241, 0.15);
    --card-bg: #171a24;
    --border: #262a38;
}

h1 { font-weight: 800 !important; letter-spacing: -0.02em; }
h2, h3 { font-weight: 700 !important; letter-spacing: -0.01em; }

/* KPI metric cards */
div[data-testid="stMetric"] {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.1rem 1.3rem;
}
div[data-testid="stMetricValue"] { font-size: 1.75rem; font-weight: 700; }
div[data-testid="stMetricLabel"] {
    font-size: 0.78rem; color: #8b90a3;
    text-transform: uppercase; letter-spacing: 0.06em;
}

/* Multiselect / tag pills */
span[data-baseweb="tag"] {
    background-color: var(--accent) !important;
    border-radius: 6px !important;
}
div[data-baseweb="select"] > div {
    border-radius: 10px !important;
    background-color: var(--card-bg) !important;
    border-color: var(--border) !important;
}

/* Tabs */
button[data-baseweb="tab"] { font-weight: 500; font-size: 0.95rem; }
div[data-baseweb="tab-highlight"] { background-color: var(--accent) !important; }
div[data-baseweb="tab-border"] { background-color: var(--border) !important; }

/* Sidebar */
section[data-testid="stSidebar"] {
    border-right: 1px solid var(--border);
}
section[data-testid="stSidebar"] .streamlit-expanderHeader {
    font-weight: 500; border-radius: 8px;
}
div[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    background: var(--card-bg);
}

/* Buttons */
div.stButton > button {
    border-radius: 8px; border: 1px solid var(--border); font-weight: 500;
}

/* Reduce Streamlit's default top padding reserved for its floating toolbar */
div.block-container {
    padding-top: 2rem;
}

/* Dataframe / containers */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 12px !important;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_resource
def get_engine():
    url = os.getenv("SUPABASE_DATABASE_URL")
    if not url:
        st.error(
            "SUPABASE_DATABASE_URL not found. Add it to your .env file at the "
            "project root, e.g.\n\nSUPABASE_DATABASE_URL=postgresql://...supabase.com:5432/postgres"
        )
        st.stop()
    return create_engine(url, pool_pre_ping=True)


@st.cache_data(ttl=600, show_spinner=False)
def run_query(sql: str, params: dict | None = None, list_params: list[str] | None = None) -> pd.DataFrame:
    """Run a parameterized query. list_params = keys in `params` that are lists (for IN clauses)."""
    engine = get_engine()
    stmt = text(sql)
    if list_params:
        for key in list_params:
            stmt = stmt.bindparams(bindparam(key, expanding=True))
    with engine.connect() as conn:
        return pd.read_sql(stmt, conn, params=params or {})


# ----------------------------------------------------------------------
# Filter options (cached longer, changes rarely)
# ----------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def load_filter_options():
    df = run_query("""
        SELECT DISTINCT
            neighbourhood_group_cleansed AS region,
            neighbourhood_cleansed       AS neighbourhood,
            room_type,
            property_type
        FROM listings_master
        WHERE flag_invalid IS NOT TRUE
    """)
    bounds = run_query("""
        SELECT
            MIN(price_clean) AS min_price, MAX(price_clean) AS max_price,
            MIN(review_scores_rating) AS min_rating, MAX(review_scores_rating) AS max_rating,
            MIN(accommodates) AS min_acc, MAX(accommodates) AS max_acc
        FROM listings_master
        WHERE flag_invalid IS NOT TRUE
    """).iloc[0]
    return df, bounds


opts_df, bounds = load_filter_options()

# ----------------------------------------------------------------------
# Sidebar — cascading filters
# ----------------------------------------------------------------------
with st.sidebar:
    st.markdown("## Filters")

    if st.button("Reset all filters", use_container_width=True):
        for k in ["region_filter", "neigh_filter", "room_filter", "prop_filter",
                  "superhost_filter", "price_filter", "rating_filter", "acc_filter"]:
            st.session_state.pop(k, None)
        st.rerun()

    st.markdown("")

    regions = sorted(opts_df["region"].dropna().unique())
    with st.expander("Region", expanded=True):
        selected_regions = st.multiselect(
            "Region", regions, default=regions, key="region_filter", label_visibility="collapsed"
        )

    neigh_pool = opts_df[opts_df["region"].isin(selected_regions)] if selected_regions else opts_df
    neighbourhoods = sorted(neigh_pool["neighbourhood"].dropna().unique())
    with st.expander(f"Neighbourhood · {len(neighbourhoods)} available", expanded=False):
        selected_neighbourhoods = st.multiselect(
            "Neighbourhood", neighbourhoods, default=neighbourhoods, key="neigh_filter",
            label_visibility="collapsed",
            help="Narrows automatically based on Region selected above",
        )

    room_types = sorted(opts_df["room_type"].dropna().unique())
    with st.expander("Room type", expanded=False):
        selected_room_types = st.multiselect(
            "Room type", room_types, default=room_types, key="room_filter", label_visibility="collapsed"
        )

    property_types = sorted(opts_df["property_type"].dropna().unique())
    with st.expander("Property type", expanded=False):
        selected_property_types = st.multiselect(
            "Property type", property_types, default=property_types, key="prop_filter",
            label_visibility="collapsed",
        )

    superhost_choice = st.radio(
        "Host type", ["All", "Superhosts only", "Non-superhosts only"], index=0, key="superhost_filter"
    )

    with st.expander("Numeric ranges", expanded=False):
        price_min = int(bounds["min_price"] or 0)
        price_max = int(bounds["max_price"] or 1000)
        selected_price = st.slider(
            "Price per night (CHF)", price_min, price_max, (price_min, price_max), key="price_filter"
        )

        rating_min = float(bounds["min_rating"] or 0)
        rating_max = float(bounds["max_rating"] or 5)
        selected_rating = st.slider(
            "Rating", rating_min, rating_max, (rating_min, rating_max), key="rating_filter"
        )

        acc_min = int(bounds["min_acc"] or 1)
        acc_max = int(bounds["max_acc"] or 16)
        selected_acc = st.slider(
            "Accommodates", acc_min, acc_max, (acc_min, acc_max), key="acc_filter"
        )

    st.markdown("---")
    st.caption(f"{len(opts_df):,} listing combinations in current dataset")


# ----------------------------------------------------------------------
# Build shared WHERE clause + params for listings_master-based queries
# ----------------------------------------------------------------------
def build_filters():
    clauses = ["flag_invalid IS NOT TRUE"]
    params = {}
    list_keys = []

    if selected_regions and len(selected_regions) < len(regions):
        clauses.append("neighbourhood_group_cleansed IN :regions")
        params["regions"] = selected_regions
        list_keys.append("regions")

    if selected_neighbourhoods and len(selected_neighbourhoods) < len(neighbourhoods):
        clauses.append("neighbourhood_cleansed IN :neighs")
        params["neighs"] = selected_neighbourhoods
        list_keys.append("neighs")

    if selected_room_types and len(selected_room_types) < len(room_types):
        clauses.append("room_type IN :rooms")
        params["rooms"] = selected_room_types
        list_keys.append("rooms")

    if selected_property_types and len(selected_property_types) < len(property_types):
        clauses.append("property_type IN :props")
        params["props"] = selected_property_types
        list_keys.append("props")

    if superhost_choice == "Superhosts only":
        clauses.append("host_is_superhost = 't'")
    elif superhost_choice == "Non-superhosts only":
        clauses.append("host_is_superhost = 'f'")

    clauses.append("(price_clean IS NULL OR price_clean BETWEEN :price_lo AND :price_hi)")
    params["price_lo"], params["price_hi"] = selected_price

    clauses.append("(review_scores_rating IS NULL OR review_scores_rating BETWEEN :rating_lo AND :rating_hi)")
    params["rating_lo"], params["rating_hi"] = selected_rating

    clauses.append("(accommodates IS NULL OR accommodates BETWEEN :acc_lo AND :acc_hi)")
    params["acc_lo"], params["acc_hi"] = selected_acc

    where_sql = " AND ".join(clauses)
    return where_sql, params, list_keys


WHERE_SQL, PARAMS, LIST_KEYS = build_filters()

# ----------------------------------------------------------------------
# Header
# ----------------------------------------------------------------------
st.title("Vaud Airbnb Market Dashboard")
st.caption("Data sourced from Inside Airbnb listings for the canton of Vaud, Switzerland")

tab_overview, tab_neigh, tab_pricing, tab_avail, tab_reviews, tab_hosts = st.tabs(
    ["Overview", "Neighbourhoods", "Pricing", "Availability", "Reviews", "Hosts"]
)

# ----------------------------------------------------------------------
# TAB: Overview
# ----------------------------------------------------------------------
with tab_overview:
    kpi_df = run_query(f"""
        SELECT
            COUNT(*) AS total_listings,
            AVG(price_clean) AS avg_price,
            AVG(review_scores_rating) AS avg_rating,
            AVG(CASE WHEN host_is_superhost = 't' THEN 1.0 ELSE 0 END) AS superhost_pct,
            SUM(revenue_estimate_calc) AS total_revenue,
            AVG(occupancy_rate_calc) AS avg_occupancy
        FROM listings_master
        WHERE {WHERE_SQL}
    """, PARAMS, LIST_KEYS).iloc[0]

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1, st.container(border=True):
        st.metric("Listings", f"{int(kpi_df['total_listings']):,}")
    with c2, st.container(border=True):
        st.metric("Avg price / night", f"CHF {kpi_df['avg_price']:.0f}" if pd.notna(kpi_df['avg_price']) else "—")
    with c3, st.container(border=True):
        st.metric("Avg rating", f"{kpi_df['avg_rating']:.2f}" if pd.notna(kpi_df['avg_rating']) else "—")
    with c4, st.container(border=True):
        st.metric("Superhosts", f"{kpi_df['superhost_pct']*100:.0f}%" if pd.notna(kpi_df['superhost_pct']) else "—")
    with c5, st.container(border=True):
        st.metric("Avg occupancy", f"{kpi_df['avg_occupancy']*100:.0f}%" if pd.notna(kpi_df['avg_occupancy']) else "—")

    st.markdown("")
    col1, col2 = st.columns([1.1, 1])

    with col1:
        room_df = run_query(f"""
            SELECT room_type, COUNT(*) AS n
            FROM listings_master
            WHERE {WHERE_SQL}
            GROUP BY room_type ORDER BY n DESC
        """, PARAMS, LIST_KEYS)
        fig = px.pie(room_df, names="room_type", values="n", title="Listings by room type", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        map_color = st.radio("Colour by", ["price_clean", "review_scores_rating"], horizontal=True,
                              format_func=lambda x: "Price" if x == "price_clean" else "Rating",
                              key="map_color_choice", label_visibility="collapsed")

        map_df = run_query(f"""
            SELECT latitude, longitude, price_clean, review_scores_rating,
                   name, room_type, neighbourhood_cleansed
            FROM listings_master
            WHERE {WHERE_SQL} AND latitude IS NOT NULL AND longitude IS NOT NULL
            LIMIT 5000
        """, PARAMS, LIST_KEYS)

        if map_df.empty:
            st.info("No listings match the current filters.")
        else:
            fig = px.scatter_mapbox(
                map_df, lat="latitude", lon="longitude", color=map_color,
                hover_name="name", hover_data=["neighbourhood_cleansed", "room_type"],
                color_continuous_scale="Viridis", zoom=7, height=330,
            )
            fig.update_layout(
                mapbox_style="carto-positron",
                margin=dict(l=0, r=0, t=0, b=0),
                showlegend=False,
                coloraxis_colorbar=dict(thickness=10, len=0.8),
            )
            st.plotly_chart(fig, use_container_width=True)

    top_neigh_df = run_query(f"""
        SELECT neighbourhood_cleansed AS neighbourhood, COUNT(*) AS listings,
               AVG(price_clean) AS avg_price, AVG(review_scores_rating) AS avg_rating
        FROM listings_master
        WHERE {WHERE_SQL}
        GROUP BY neighbourhood_cleansed
        ORDER BY listings DESC LIMIT 15
    """, PARAMS, LIST_KEYS)
    fig = px.bar(top_neigh_df, x="neighbourhood", y="listings", title="Top 15 neighbourhoods by listing count",
                 hover_data=["avg_price", "avg_rating"])
    st.plotly_chart(fig, use_container_width=True)

    price_df = run_query(f"""
        SELECT price_clean FROM listings_master
        WHERE {WHERE_SQL} AND price_clean IS NOT NULL AND price_clean < 2000
    """, PARAMS, LIST_KEYS)
    fig = px.histogram(price_df, x="price_clean", nbins=50, title="Price distribution (CHF/night)")
    fig.update_layout(xaxis_title="Price (CHF)", yaxis_title="Listings")
    st.plotly_chart(fig, use_container_width=True)

# ----------------------------------------------------------------------
# TAB: Neighbourhoods
# ----------------------------------------------------------------------
with tab_neigh:
    region_df = run_query(f"""
        SELECT neighbourhood_group_cleansed AS region, COUNT(*) AS listings,
               AVG(price_clean) AS avg_price, AVG(review_scores_rating) AS avg_rating
        FROM listings_master
        WHERE {WHERE_SQL}
        GROUP BY neighbourhood_group_cleansed
        ORDER BY listings DESC
    """, PARAMS, LIST_KEYS)

    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(region_df, x="region", y="avg_price", title="Avg price by region (district)",
                     color="avg_rating", color_continuous_scale="RdYlGn")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = px.bar(region_df, x="region", y="listings", title="Listing count by region")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Neighbourhood detail table")
    full_neigh_df = run_query(f"""
        SELECT neighbourhood_cleansed AS neighbourhood, neighbourhood_group_cleansed AS region,
               COUNT(*) AS listings, AVG(price_clean) AS avg_price,
               AVG(review_scores_rating) AS avg_rating,
               AVG(CASE WHEN host_is_superhost = 't' THEN 1.0 ELSE 0 END) AS superhost_pct
        FROM listings_master
        WHERE {WHERE_SQL}
        GROUP BY neighbourhood_cleansed, neighbourhood_group_cleansed
        ORDER BY listings DESC
    """, PARAMS, LIST_KEYS)
    full_neigh_df["avg_price"] = full_neigh_df["avg_price"].round(0)
    full_neigh_df["avg_rating"] = full_neigh_df["avg_rating"].round(2)
    full_neigh_df["superhost_pct"] = (full_neigh_df["superhost_pct"] * 100).round(0)
    st.dataframe(full_neigh_df, use_container_width=True, hide_index=True)

# ----------------------------------------------------------------------
# TAB: Pricing
# ----------------------------------------------------------------------
with tab_pricing:
    price_room_df = run_query(f"""
        SELECT room_type, price_clean FROM listings_master
        WHERE {WHERE_SQL} AND price_clean IS NOT NULL AND price_clean < 2000
    """, PARAMS, LIST_KEYS)
    fig = px.box(price_room_df, x="room_type", y="price_clean", title="Price distribution by room type")
    st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        acc_price_df = run_query(f"""
            SELECT accommodates, AVG(price_clean) AS avg_price, COUNT(*) AS n
            FROM listings_master
            WHERE {WHERE_SQL} AND price_clean IS NOT NULL
            GROUP BY accommodates ORDER BY accommodates
        """, PARAMS, LIST_KEYS)
        fig = px.line(acc_price_df, x="accommodates", y="avg_price", markers=True,
                      title="Avg price vs. accommodates")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        rating_price_df = run_query(f"""
            SELECT review_scores_rating, price_clean, room_type
            FROM listings_master
            WHERE {WHERE_SQL} AND price_clean IS NOT NULL AND price_clean < 2000
              AND review_scores_rating IS NOT NULL
            LIMIT 3000
        """, PARAMS, LIST_KEYS)
        fig = px.scatter(rating_price_df, x="review_scores_rating", y="price_clean", color="room_type",
                         opacity=0.5, title="Price vs. rating")
        st.plotly_chart(fig, use_container_width=True)

# ----------------------------------------------------------------------
# TAB: Availability
# ----------------------------------------------------------------------
with tab_avail:
    st.caption("Availability trend aggregated by month across matching listings' calendar entries")

    avail_trend_df = run_query(f"""
        SELECT d.year, d.month, d.month_name,
               AVG(CASE WHEN fc.is_available THEN 1.0 ELSE 0 END) AS availability_rate,
               COUNT(*) AS n
        FROM fact_calendar fc
        JOIN dim_date d ON fc.date_id = d.date_id
        JOIN listings_master lm ON fc.listing_key = lm.id
        WHERE {WHERE_SQL}
        GROUP BY d.year, d.month, d.month_name
        ORDER BY d.year, d.month
    """, PARAMS, LIST_KEYS)

    if avail_trend_df.empty:
        st.info("No calendar data matches the current filters.")
    else:
        avail_trend_df["period"] = avail_trend_df["month_name"].str.slice(0, 3) + " " + avail_trend_df["year"].astype(str)
        fig = px.line(avail_trend_df, x="period", y="availability_rate", markers=True,
                     title="Availability rate over time")
        fig.update_layout(yaxis_tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        avail365_df = run_query(f"""
            SELECT availability_365 FROM listings_master
            WHERE {WHERE_SQL} AND availability_365 IS NOT NULL
        """, PARAMS, LIST_KEYS)
        fig = px.histogram(avail365_df, x="availability_365", nbins=40, title="Days available in next 365 (distribution)")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        occ_df = run_query(f"""
            SELECT occupancy_rate_calc FROM listings_master
            WHERE {WHERE_SQL} AND occupancy_rate_calc IS NOT NULL
        """, PARAMS, LIST_KEYS)
        fig = px.histogram(occ_df, x="occupancy_rate_calc", nbins=40, title="Occupancy rate (distribution)")
        fig.update_layout(xaxis_tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)

# ----------------------------------------------------------------------
# TAB: Reviews
# ----------------------------------------------------------------------
with tab_reviews:
    review_trend_df = run_query(f"""
        SELECT d.year, d.month,
               COUNT(*) AS review_count
        FROM fact_reviews fr
        JOIN dim_date d ON fr.date_id = d.date_id
        JOIN listings_master lm ON fr.listing_key = lm.id
        WHERE {WHERE_SQL}
        GROUP BY d.year, d.month
        ORDER BY d.year, d.month
    """, PARAMS, LIST_KEYS)

    if review_trend_df.empty:
        st.info("No review data matches the current filters.")
    else:
        review_trend_df["period"] = pd.to_datetime(
            review_trend_df["year"].astype(str) + "-" + review_trend_df["month"].astype(str) + "-01"
        )
        fig = px.line(review_trend_df, x="period", y="review_count", title="Review volume over time")
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns([1, 1])
    with col1:
        score_cols = ["review_scores_accuracy", "review_scores_cleanliness", "review_scores_checkin",
                      "review_scores_communication", "review_scores_location", "review_scores_value"]
        score_df = run_query(f"""
            SELECT {', '.join(f'AVG({c}) AS {c}' for c in score_cols)}
            FROM listings_master WHERE {WHERE_SQL}
        """, PARAMS, LIST_KEYS).iloc[0]

        categories = [c.replace("review_scores_", "").capitalize() for c in score_cols]
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(r=score_df.values.astype(float), theta=categories, fill='toself'))
        fig.update_layout(title="Avg review sub-scores", polar=dict(radialaxis=dict(range=[0, 5])))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("#### Recent reviews (sample)")
        recent_df = run_query(f"""
            SELECT rt.comments, lm.name AS listing_name, lm.neighbourhood_cleansed AS neighbourhood
            FROM reviews_text rt
            JOIN listings_master lm ON rt.listing_key = lm.id
            WHERE {WHERE_SQL} AND rt.comments IS NOT NULL
            ORDER BY rt.date_id DESC
            LIMIT 10
        """, PARAMS, LIST_KEYS)
        for _, row in recent_df.iterrows():
            with st.container(border=True):
                st.caption(f"{row['listing_name']} · {row['neighbourhood']}")
                # Scraped review text sometimes contains literal HTML line
                # breaks — convert to real newlines rather than showing the tag.
                clean_comment = re.sub(r"<br\s*/?>", "\n\n", row["comments"])
                st.write(clean_comment[:280] + ("…" if len(clean_comment) > 280 else ""))

# ----------------------------------------------------------------------
# TAB: Hosts
# ----------------------------------------------------------------------
with tab_hosts:
    host_compare_df = run_query(f"""
        SELECT
            CASE WHEN host_is_superhost = 't' THEN 'Superhost' ELSE 'Regular host' END AS host_type,
            COUNT(*) AS listings,
            AVG(price_clean) AS avg_price,
            AVG(review_scores_rating) AS avg_rating,
            AVG(number_of_reviews) AS avg_reviews,
            AVG(host_tenure_years) AS avg_tenure
        FROM listings_master
        WHERE {WHERE_SQL} AND host_is_superhost IN ('t', 'f')
        GROUP BY host_is_superhost
    """, PARAMS, LIST_KEYS)

    st.dataframe(host_compare_df.round(2), use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(host_compare_df, x="host_type", y="avg_price", title="Avg price: superhost vs regular")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = px.bar(host_compare_df, x="host_type", y="avg_rating", title="Avg rating: superhost vs regular")
        fig.update_yaxes(range=[0, 5])
        st.plotly_chart(fig, use_container_width=True)

    top_hosts_df = run_query(f"""
        SELECT host_name, COUNT(*) AS num_listings, AVG(price_clean) AS avg_price
        FROM listings_master
        WHERE {WHERE_SQL} AND host_name IS NOT NULL
        GROUP BY host_name
        ORDER BY num_listings DESC
        LIMIT 15
    """, PARAMS, LIST_KEYS)
    fig = px.bar(top_hosts_df, x="host_name", y="num_listings", title="Top 15 hosts by number of listings",
                 hover_data=["avg_price"])
    st.plotly_chart(fig, use_container_width=True)
