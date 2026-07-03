"""
Export report-quality chart images from Supabase for the Word report,
section 10 (Visualizations).

Run:
    pip install matplotlib seaborn
    python export_report_charts.py

Outputs to ./report_assets/:
    fig01_room_type.png
    fig02_price_distribution.png
    fig03_top_neighbourhoods.png
    fig04_avg_price_by_region.png
    fig05_price_by_room_type.png
    fig06_availability_trend.png
    fig07_review_volume_trend.png
    fig08_superhost_comparison.png
    summary_stats.json   <- exact numbers to reference in report captions/text

Send the whole report_assets/ folder (or the images + summary_stats.json)
back so the actual Word document can be built with real figures and
accurate interpretation text instead of placeholders.
"""

import os
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("SUPABASE_DATABASE_URL")
assert DB_URL, "Set SUPABASE_DATABASE_URL in your .env file first"
engine = create_engine(DB_URL, pool_pre_ping=True)

OUT_DIR = "report_assets"
os.makedirs(OUT_DIR, exist_ok=True)

ACCENT = "#6366f1"
sns.set_theme(style="whitegrid", rc={
    "figure.dpi": 300,
    "font.family": "sans-serif",
    "axes.edgecolor": "#333333",
})


def q(sql):
    return pd.read_sql(text(sql), engine)


def save(fig, name):
    path = os.path.join(OUT_DIR, name)
    fig.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


summary = {}

# ----------------------------------------------------------------------
# Fig 1 — Listings by room type
# ----------------------------------------------------------------------
room_df = q("""
    SELECT room_type, COUNT(*) AS n
    FROM listings_master WHERE flag_invalid IS NOT TRUE
    GROUP BY room_type ORDER BY n DESC
""")
fig, ax = plt.subplots(figsize=(7, 5))
ax.pie(room_df["n"], labels=room_df["room_type"], autopct="%1.1f%%",
       colors=sns.color_palette("Blues_r", len(room_df)), startangle=90)
ax.set_title("Listings by Room Type", fontsize=13, fontweight="bold")
save(fig, "fig01_room_type.png")
summary["room_type_breakdown"] = room_df.to_dict(orient="records")

# ----------------------------------------------------------------------
# Fig 2 — Price distribution
# ----------------------------------------------------------------------
price_df = q("""
    SELECT price_clean FROM listings_master
    WHERE flag_invalid IS NOT TRUE AND price_clean IS NOT NULL AND price_clean < 2000
""")
fig, ax = plt.subplots(figsize=(8, 5))
sns.histplot(price_df["price_clean"], bins=50, color=ACCENT, ax=ax)
ax.set_xlabel("Price per night (CHF)")
ax.set_ylabel("Number of listings")
ax.set_title("Price Distribution", fontsize=13, fontweight="bold")
save(fig, "fig02_price_distribution.png")
summary["price_stats"] = {
    "mean": round(price_df["price_clean"].mean(), 2),
    "median": round(price_df["price_clean"].median(), 2),
    "std": round(price_df["price_clean"].std(), 2),
    "min": round(price_df["price_clean"].min(), 2),
    "max": round(price_df["price_clean"].max(), 2),
}

# ----------------------------------------------------------------------
# Fig 3 — Top 15 neighbourhoods by listing count
# ----------------------------------------------------------------------
top_neigh_df = q("""
    SELECT neighbourhood_cleansed AS neighbourhood, COUNT(*) AS listings,
           AVG(price_clean) AS avg_price
    FROM listings_master WHERE flag_invalid IS NOT TRUE
    GROUP BY neighbourhood_cleansed ORDER BY listings DESC LIMIT 15
""")
fig, ax = plt.subplots(figsize=(9, 5.5))
sns.barplot(data=top_neigh_df, x="listings", y="neighbourhood", color=ACCENT, ax=ax)
ax.set_xlabel("Number of listings")
ax.set_ylabel("")
ax.set_title("Top 15 Neighbourhoods by Listing Count", fontsize=13, fontweight="bold")
save(fig, "fig03_top_neighbourhoods.png")
summary["top_neighbourhoods"] = top_neigh_df.round(1).to_dict(orient="records")

# ----------------------------------------------------------------------
# Fig 4 — Avg price by region
# ----------------------------------------------------------------------
region_df = q("""
    SELECT neighbourhood_group_cleansed AS region, COUNT(*) AS listings,
           AVG(price_clean) AS avg_price, AVG(review_scores_rating) AS avg_rating
    FROM listings_master WHERE flag_invalid IS NOT TRUE
    GROUP BY neighbourhood_group_cleansed ORDER BY avg_price DESC
""")
fig, ax = plt.subplots(figsize=(9, 5))
sns.barplot(data=region_df, x="avg_price", y="region", color=ACCENT, ax=ax)
ax.set_xlabel("Average price per night (CHF)")
ax.set_ylabel("")
ax.set_title("Average Price by Region", fontsize=13, fontweight="bold")
save(fig, "fig04_avg_price_by_region.png")
summary["region_stats"] = region_df.round(2).to_dict(orient="records")

# ----------------------------------------------------------------------
# Fig 5 — Price distribution by room type (box plot)
# ----------------------------------------------------------------------
price_room_df = q("""
    SELECT room_type, price_clean FROM listings_master
    WHERE flag_invalid IS NOT TRUE AND price_clean IS NOT NULL AND price_clean < 2000
""")
fig, ax = plt.subplots(figsize=(8, 5))
sns.boxplot(data=price_room_df, x="room_type", y="price_clean",
            hue="room_type", palette="Blues", legend=False, ax=ax)
ax.set_xlabel("Room type")
ax.set_ylabel("Price per night (CHF)")
ax.set_title("Price Distribution by Room Type", fontsize=13, fontweight="bold")
plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
save(fig, "fig05_price_by_room_type.png")
summary["price_by_room_type"] = (
    price_room_df.groupby("room_type")["price_clean"].median().round(1).to_dict()
)

# ----------------------------------------------------------------------
# Fig 6 — Availability trend over time
# ----------------------------------------------------------------------
avail_df = q("""
    SELECT d.year, d.month, d.month_name,
           AVG(CASE WHEN fc.is_available THEN 1.0 ELSE 0 END) AS availability_rate
    FROM fact_calendar fc
    JOIN dim_date d ON fc.date_id = d.date_id
    GROUP BY d.year, d.month, d.month_name
    ORDER BY d.year, d.month
""")
avail_df["period"] = avail_df["month_name"].str.slice(0, 3) + " " + avail_df["year"].astype(str)
fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(avail_df["period"], avail_df["availability_rate"] * 100, marker="o", color=ACCENT)
ax.set_xlabel("Month")
ax.set_ylabel("Availability rate (%)")
ax.set_title("Availability Rate Over Time", fontsize=13, fontweight="bold")
plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
ax.xaxis.set_major_locator(plt.MaxNLocator(12))
save(fig, "fig06_availability_trend.png")
summary["availability_trend"] = avail_df.round(3).to_dict(orient="records")

# ----------------------------------------------------------------------
# Fig 7 — Review volume trend over time
# ----------------------------------------------------------------------
review_trend_df = q("""
    SELECT d.year, d.month, COUNT(*) AS review_count
    FROM fact_reviews fr
    JOIN dim_date d ON fr.date_id = d.date_id
    GROUP BY d.year, d.month ORDER BY d.year, d.month
""")
review_trend_df["period"] = pd.to_datetime(
    review_trend_df["year"].astype(str) + "-" + review_trend_df["month"].astype(str) + "-01"
)
fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(review_trend_df["period"], review_trend_df["review_count"], color=ACCENT)
ax.set_xlabel("Date")
ax.set_ylabel("Number of reviews")
ax.set_title("Review Volume Over Time", fontsize=13, fontweight="bold")
save(fig, "fig07_review_volume_trend.png")
summary["total_reviews"] = int(review_trend_df["review_count"].sum())

# ----------------------------------------------------------------------
# Fig 8 — Superhost vs regular host comparison
# ----------------------------------------------------------------------
host_df = q("""
    SELECT CASE WHEN host_is_superhost = 't' THEN 'Superhost' ELSE 'Regular host' END AS host_type,
           COUNT(*) AS listings, AVG(price_clean) AS avg_price,
           AVG(review_scores_rating) AS avg_rating, AVG(number_of_reviews) AS avg_reviews
    FROM listings_master
    WHERE flag_invalid IS NOT TRUE AND host_is_superhost IN ('t', 'f')
    GROUP BY host_is_superhost
""")
fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
sns.barplot(data=host_df, x="host_type", y="avg_price", hue="host_type",
            palette="Blues", legend=False, ax=axes[0])
axes[0].set_title("Avg Price", fontsize=11, fontweight="bold")
axes[0].set_xlabel("")
axes[0].set_ylabel("CHF / night")
sns.barplot(data=host_df, x="host_type", y="avg_rating", hue="host_type",
            palette="Blues", legend=False, ax=axes[1])
axes[1].set_title("Avg Rating", fontsize=11, fontweight="bold")
axes[1].set_xlabel("")
axes[1].set_ylabel("Rating (out of 5)")
axes[1].set_ylim(0, 5)
fig.suptitle("Superhost vs. Regular Host Comparison", fontsize=13, fontweight="bold")
save(fig, "fig08_superhost_comparison.png")
summary["host_comparison"] = host_df.round(2).to_dict(orient="records")

# ----------------------------------------------------------------------
# Write summary stats
# ----------------------------------------------------------------------
with open(os.path.join(OUT_DIR, "summary_stats.json"), "w") as f:
    json.dump(summary, f, indent=2, default=str)

print(f"\nDone. {len(os.listdir(OUT_DIR))} files written to {OUT_DIR}/")
print("Send the report_assets folder back (zip it if easier) so the Word doc can be built.")
