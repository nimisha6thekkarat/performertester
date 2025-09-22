import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd

# ---------------------------
# Helpers
# ---------------------------

def parse_html_report(file):
    """Extract key metrics and tables from a performance HTML report."""
    soup = BeautifulSoup(file.read(), "html.parser")

    # Overall Results
    overall_table = soup.find("h2", string="Overall Result").find_next("table")
    overall_data = {
        row.find_all("th")[0].text.strip(): row.find_all("td")[0].text.strip()
        for row in overall_table.find_all("tr")
    }

    # Transaction Summary
    txn_table = soup.find("h2", string="Transactions Summary").find_next("table")
    txn_rows = []
    for row in txn_table.find_all("tr")[1:]:  # skip header
        cols = [col.text.strip() for col in row.find_all("td")]
        if cols:
            txn_rows.append(cols)
    txn_df = pd.DataFrame(
        txn_rows,
        columns=["Transaction", "Requests", "Avg Time", "95th Percentile", "Errors", "Missed Goals"]
    )

    # Convert numeric columns
    for col in ["Requests", "Avg Time", "95th Percentile", "Errors", "Missed Goals"]:
        txn_df[col] = pd.to_numeric(txn_df[col], errors="coerce")

    return overall_data, txn_df


def highlight_diff(series, better="lower"):
    """Highlight best/worst values in a Series."""
    if series.empty:
        return [""] * len(series)

    if better == "lower":
        best, worst = series.min(), series.max()
    else:
        best, worst = series.max(), series.min()

    return [
        "background-color: lightgreen" if v == best else
        "background-color: salmon" if v == worst else ""
        for v in series
    ]


# ---------------------------
# Streamlit App
# ---------------------------

st.title("📊 Performance Test Report Comparator")

uploaded_files = st.file_uploader(
    "Upload HTML performance reports",
    type=["html"],
    accept_multiple_files=True
)

if uploaded_files:
    all_overall = []
    txn_dfs = {}

    # Parse each uploaded file
    for file in uploaded_files:
        overall, txn_df = parse_html_report(file)
        all_overall.append(overall)
        txn_dfs[file.name] = txn_df

    # ---------------------------
    # Overall Results Comparison
    # ---------------------------
    st.subheader("Overall Results Comparison")

    overall_df = pd.DataFrame(all_overall, index=[f.name for f in uploaded_files])

    # Normalize column names
    normalized_columns = [
        c.strip().replace(" ", "_").replace("%", "pct").replace("(", "").replace(")", "").lower()
        for c in overall_df.columns
    ]
    overall_df.columns = normalized_columns

    # Dynamically map key metrics
    col_map = {}
    for col in overall_df.columns:
        if "avg" in col and "time" in col:
            col_map["avg_response_time"] = col
        if "failed" in col and "pct" in col:
            col_map["failed_requests"] = col
        if "requests" in col and "sec" in col:
            col_map["requests_sec"] = col

    if not col_map:
        st.error("⚠ Could not detect required columns in Overall Results. Check your HTML format.")
        st.write("Available columns:", overall_df.columns.tolist())
        st.stop()

    # Convert numeric where possible
    for col in overall_df.columns:
        overall_df[col] = pd.to_numeric(overall_df[col], errors="ignore")

    # Style highlights using subset
    styled = overall_df.style
    if "avg_response_time" in col_map:
        styled = styled.apply(highlight_diff, subset=[col_map["avg_response_time"]], better="lower")
    if "failed_requests" in col_map:
        styled = styled.apply(highlight_diff, subset=[col_map["failed_requests"]], better="lower")
    if "requests_sec" in col_map:
        styled = styled.apply(highlight_diff, subset=[col_map["requests_sec"]], better="higher")

    st.dataframe(styled, use_container_width=True)

    # ---------------------------
    # Transaction Summary Comparison
    # ---------------------------
    st.subheader("Transaction Summary Comparison")

    combined_txns = None
    for fname, df in txn_dfs.items():
        df = df.copy()
        df["Report"] = fname
        combined_txns = pd.concat([combined_txns, df]) if combined_txns is not None else df

    st.dataframe(combined_txns, use_container_width=True)

    # ---------------------------
    # Per-Transaction Highlights
    # ---------------------------
    st.subheader("Per-Transaction Performance Highlights")

    for txn_name in combined_txns["Transaction"].unique():
        subset = combined_txns[combined_txns["Transaction"] == txn_name].set_index("Report")
        styled_txn = subset.style
        if "Avg Time" in subset.columns:
            styled_txn = styled_txn.apply(highlight_diff, subset=["Avg Time"], better="lower")
        if "95th Percentile" in subset.columns:
            styled_txn = styled_txn.apply(highlight_diff, subset=["95th Percentile"], better="lower")

        st.markdown(f"### {txn_name}")
        st.dataframe(styled_txn, use_container_width=True)
