import io
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(page_title="MetaRibosomics Explorer", layout="wide")


RANKS = ["phylum", "class", "order", "family", "genus", "species"]
DATASET_KEYS = ["LSU counts", "SSU counts", "LSU abundance", "SSU abundance"]


@dataclass
class TableData:
    loaded: bool = False
    file_name: str = "Not uploaded"
    df: Optional[pd.DataFrame] = None


def parse_tsv(uploaded_file) -> pd.DataFrame:
    """Parse a SILVA-like tab-delimited table.

    Expected format:
    Taxonomy<TAB>Length<TAB>sample1<TAB>sample2...
    """
    if uploaded_file is None:
        return pd.DataFrame()

    text = uploaded_file.getvalue().decode("utf-8", errors="replace")
    df = pd.read_csv(io.StringIO(text), sep="\t")

    if df.shape[1] < 3:
        raise ValueError("The table must have at least three columns: Taxonomy, Length, and one sample column.")

    if "Taxonomy" not in df.columns or "Length" not in df.columns:
        # Be forgiving for minor header differences
        cols = list(df.columns)
        cols[0] = "Taxonomy"
        cols[1] = "Length"
        df.columns = cols

    df["Taxonomy"] = df["Taxonomy"].astype(str)
    df["Length"] = pd.to_numeric(df["Length"], errors="coerce").fillna(0).astype(int)
    for c in df.columns[2:]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

    return df


def split_taxonomy(taxonomy: str) -> List[str]:
    return [x.strip() for x in str(taxonomy).split(";") if x.strip()]


def get_rank_label(taxonomy: str, rank: str) -> str:
    parts = split_taxonomy(taxonomy)
    if not parts:
        return "Unclassified"

    # Best-effort SILVA-style rank extraction.
    # Common patterns:
    # Eukaryota;SAR;Alveolata;Dinoflagellata;...
    # Bacteria;Bacteroidota;Bacteroidia;Bacteroidales;...
    idx_map = {"phylum": 1, "class": 2, "order": 3, "family": 4, "genus": 5, "species": 6}
    idx = idx_map.get(rank)
    if idx is not None and idx < len(parts):
        return parts[idx]
    return parts[-1]


def weighted_mean(df: pd.DataFrame, sample_col: str) -> float:
    total = df[sample_col].sum()
    if total == 0:
        return float("nan")
    return float((df["Length"] * df[sample_col]).sum() / total)


def weighted_mean_all(df: pd.DataFrame, sample_cols: List[str]) -> Tuple[float, int]:
    counts = df[sample_cols].sum(axis=1)
    total = int(counts.sum())
    if total == 0:
        return float("nan"), 0
    weighted = float((df["Length"] * counts).sum() / total)
    return weighted, total


@st.cache_data(show_spinner=False)
def filter_rows(df: pd.DataFrame, query: str, mode: str, rank: str) -> pd.DataFrame:
    q = query.strip().lower()
    if not q or df.empty:
        return df.iloc[0:0].copy()
    if mode == "taxon":
        mask = df["Taxonomy"].str.lower().str.contains(q, na=False)
    else:
        mask = df["Taxonomy"].apply(lambda x: q in get_rank_label(x, rank).lower())
    return df.loc[mask].copy()


@st.cache_data(show_spinner=False)
def build_plot_frame(df: pd.DataFrame, sample_cols: List[str], selected_samples: Optional[List[str]] = None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Sample", "Weighted length (bp)", "Total counts"])

    if selected_samples is None or len(selected_samples) == 0:
        selected_samples = sample_cols

    rows = []
    for sample in selected_samples:
        total = int(df[sample].sum())
        weighted = weighted_mean(df, sample) if total else float("nan")
        rows.append({"Sample": sample, "Weighted length (bp)": weighted, "Total counts": total})
    return pd.DataFrame(rows)


st.title("MetaRibosomics Explorer")
st.caption(
    "Upload LSU and SSU tables separately. LSU/SSU abundance tables can be uploaded separately too. Biomass calculations can be added later."
)

with st.sidebar:
    st.header("Upload files")
    st.write("Load each file separately.")

    uploaded_files: Dict[str, Optional[object]] = {}
    datasets: Dict[str, TableData] = {}

    for key in DATASET_KEYS:
        uploaded_files[key] = st.file_uploader(key, type=["txt", "tsv", "csv"], key=key.replace(" ", "_").lower())

    st.divider()
    st.subheader("Analysis settings")
    mode = st.radio("Compare by", ["taxon", "rank"], horizontal=True)
    rank = st.selectbox("Taxonomic rank", RANKS, index=0, disabled=(mode != "rank"))
    query = st.text_input("Search term", value="Metazoa", help="Examples: Metazoa, Dinoflagellata, Bacteria, Alveolata")

    st.divider()
    st.write("Choose the active dataset to inspect:")

# Parse uploaded files
for key, file in uploaded_files.items():
    if file is not None:
        try:
            df = parse_tsv(file)
            datasets[key] = TableData(loaded=True, file_name=file.name, df=df)
        except Exception as e:
            st.error(f"{key}: {e}")
            datasets[key] = TableData(loaded=False, file_name=file.name, df=None)
    else:
        datasets[key] = TableData()

loaded_keys = [k for k, v in datasets.items() if v.loaded]
active_dataset = st.radio(
    "Active dataset",
    options=DATASET_KEYS,
    index=0,
    horizontal=True,
)

current = datasets[active_dataset]

if not current.loaded or current.df is None:
    st.info("Upload a table in the sidebar to begin.")
    st.stop()

# Sample columns
sample_cols = list(current.df.columns[2:])

# Search/filter
filtered = filter_rows(current.df, query, mode, rank)

# Layout
left, right = st.columns([1.35, 1])

with left:
    st.subheader(f"{active_dataset} plot")

    if filtered.empty:
        st.warning("No matching taxa. Try a broader term such as Metazoa, Dinoflagellata, or Bacteria.")
    else:
        sample_focus = st.selectbox("Sample to display", ["All samples"] + sample_cols)
        if sample_focus == "All samples":
            plot_df = build_plot_frame(filtered, sample_cols)
            fig = px.line(
                plot_df,
                x="Sample",
                y="Weighted length (bp)",
                markers=True,
                title=f"Weighted length for {query} ({active_dataset})",
            )
            fig.update_layout(height=520, margin=dict(l=20, r=20, t=60, b=120))
            fig.update_xaxes(tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        else:
            plot_df = build_plot_frame(filtered, [sample_focus])
            fig = px.bar(
                plot_df,
                x="Sample",
                y="Weighted length (bp)",
                title=f"Weighted length for {query} in {sample_focus}",
            )
            fig.update_layout(height=420, margin=dict(l=20, r=20, t=60, b=60))
            st.plotly_chart(fig, use_container_width=True)

    st.download_button(
        "Download plot data as CSV",
        data=build_plot_frame(filtered, sample_cols).to_csv(index=False).encode("utf-8"),
        file_name=f"{active_dataset.replace(' ', '_')}_{query.replace(' ', '_')}_weighted_length.csv",
        mime="text/csv",
        disabled=filtered.empty,
    )

with right:
    st.subheader("Summary")
    w_all, total_counts = weighted_mean_all(filtered, sample_cols)
    c1, c2 = st.columns(2)
    c1.metric("Matched rows", f"{len(filtered):,}")
    c2.metric("Total counts", f"{total_counts:,}")
    st.metric("Weighted length (all samples)", f"{w_all:,.1f} bp" if pd.notna(w_all) else "—")

    st.markdown("### Quick examples")
    if st.button("Metazoa"):
        st.session_state["query"] = "Metazoa"
    if st.button("Dinoflagellata"):
        st.session_state["query"] = "Dinoflagellata"
    if st.button("Bacteria"):
        st.session_state["query"] = "Bacteria"

    st.markdown("### Top matching rows")
    show_df = filtered[["Taxonomy", "Length"] + sample_cols].copy()
    if mode == "rank":
        show_df[rank] = show_df["Taxonomy"].apply(lambda x: get_rank_label(x, rank))
        show_df = show_df[["Taxonomy", rank, "Length"] + sample_cols]
    st.dataframe(show_df.head(200), use_container_width=True, height=340)

st.divider()

if mode == "rank" and not filtered.empty:
    st.subheader(f"{rank.title()} groups across samples")

    grouped = []
    for gname, gdf in filtered.groupby(filtered["Taxonomy"].apply(lambda x: get_rank_label(x, rank))):
        w, total = weighted_mean_all(gdf, sample_cols)
        grouped.append({"Group": gname, "Weighted length (all samples)": w, "Total counts": total})

    group_df = pd.DataFrame(grouped).sort_values("Total counts", ascending=False)
    st.dataframe(group_df, use_container_width=True, height=260)

    bar_fig = px.bar(
        group_df.head(20),
        x="Group",
        y="Weighted length (all samples)",
        title=f"Top {rank} groups by weighted length",
    )
    bar_fig.update_layout(height=450, xaxis_tickangle=-45)
    st.plotly_chart(bar_fig, use_container_width=True)

st.caption(
    "Biomass and carbon conversion can be added later once LSU/SSU abundance tables and RNA-to-biomass conversion factors are finalized."
)
