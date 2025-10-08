import re
import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="StresStimulus Report Comparator", layout="wide")
st.title("📊 StresStimulus Performance Report Comparator")

uploaded_files = st.file_uploader(
    "Upload one or more StresStimulus HTML reports",
    type=["html"],
    accept_multiple_files=True
)

# ------------------------------------------------
# Helper: Extract summary info
# ------------------------------------------------
def parse_stresstimulus_summary(soup, file_name):
    run_info = soup.find("div", id="Test Run Information_div")
    overall_result = soup.find("div", id="Overall Result_div")
    requests = soup.find("div", id="Requests_div")

    start_time = end_time = status = max_user_load = failed_requests = "N/A"

    if run_info:
        try:
            start_time = run_info.find(string="Start time").find_next("td").text.strip()
            end_time = run_info.find(string="End time").find_next("td").text.strip()
        except AttributeError:
            pass

    if overall_result:
        try:
            status = overall_result.find(string="Pass/Fail Status").find_next("td").text.strip()
        except AttributeError:
            pass
        try:
            max_user_load = overall_result.find(string="Max User Load").find_next("td").text.strip()
        except AttributeError:
            pass

    if requests:
        try:
            failed_requests = requests.find(string="Failed Requests %").find_next("td").text.strip()
        except AttributeError:
            pass

    return {
        "Report Name": file_name,
        "Start Time": start_time,
        "End Time": end_time,
        "Pass/Fail Status": status,
        "Max User Load": max_user_load,
        "Failed Requests %": failed_requests
    }

# ------------------------------------------------
# Helper: Extract transaction average times
# ------------------------------------------------
def parse_transaction_details(soup):
    section = soup.find("div", id="Transaction details_div")
    if not section:
        return pd.DataFrame()

    table = section.find("table")
    if not table:
        return pd.DataFrame()

    rows = []
    for tr in table.find_all("tr")[1:]:
        tds = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(tds) > 8:
            rows.append({
                "Transaction name": tds[0],
                "Avg.(s)": tds[8]
            })
    return pd.DataFrame(rows)

# ------------------------------------------------
# Helper: Extract Top Errors section
# ------------------------------------------------
def parse_top_errors(soup, report_name):
    section = soup.find("div", id=re.compile(r"Top\s*Errors", re.IGNORECASE))
    if not section:
        return pd.DataFrame()

    table = section.find("table")
    if not table:
        return pd.DataFrame()

    rows = []
    for tr in table.find_all("tr")[1:]:
        tds = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(tds) >= 3:
            rows.append({
                "Testcase Name": report_name,
                "T.C.": tds[0],
                "Request Id": tds[1],
                "Error Description": tds[2]
            })
    return pd.DataFrame(rows)

# ------------------------------------------------
# Main Logic
# ------------------------------------------------
if uploaded_files and len(uploaded_files) >= 1:
    st.success(f"✅ {len(uploaded_files)} file(s) uploaded successfully")

    summary_data = []
    transactions_dict = {}
    error_rows = []

    for file in uploaded_files:
        file_content = file.read()
        soup = BeautifulSoup(file_content, "html.parser")

        summary_data.append(parse_stresstimulus_summary(soup, file.name))

        df_txn = parse_transaction_details(soup)
        if not df_txn.empty:
            transactions_dict[file.name] = df_txn.set_index("Transaction name")["Avg.(s)"]

        df_errors = parse_top_errors(soup, file.name)
        if not df_errors.empty:
            error_rows.append(df_errors)

    # ---------------- Table Details ----------------
    st.header("🕒 Table Details")
    df_details = pd.DataFrame(summary_data)
    st.dataframe(df_details, use_container_width=True)

    # ---------------- Avg Response Time Comparison ----------------
    if len(transactions_dict) > 1:
        st.header("⚡ Avg Response Time Comparison")

        sla_value = st.number_input(
            "Enter Response Time SLA (seconds):",
            min_value=0.0, step=0.1, value=1.0,
            help="Transactions with average response time greater than this will be highlighted in red and counted in the pie chart."
        )

        combined_df = pd.concat(transactions_dict, axis=1)
        combined_df.columns = [c for c in transactions_dict.keys()]
        combined_df = combined_df.reset_index().rename(columns={"index": "Transaction name"})

        for col in combined_df.columns[1:]:
            combined_df[col] = pd.to_numeric(combined_df[col], errors="coerce")

        # Highlight values above SLA
        def highlight_sla(val):
            try:
                return "background-color: #ffcccc" if val > sla_value else ""
            except:
                return ""

        styled_df = combined_df.style.applymap(highlight_sla, subset=combined_df.columns[1:])
        st.dataframe(styled_df, use_container_width=True)

        # ---------------- SLA Pie Chart ----------------
        st.subheader("🥧 SLA Compliance Distribution")

        # Combine all report columns to get total transactions and count SLA breaches
        all_values = combined_df.melt(id_vars=["Transaction name"], var_name="Report", value_name="Avg(s)")
        all_values["Within SLA"] = all_values["Avg(s)"] <= sla_value

        within_sla = all_values["Within SLA"].sum()
        above_sla = len(all_values) - within_sla

        labels = ["Within SLA", "Above SLA"]
        sizes = [within_sla, above_sla]
        colors = ["#90ee90", "#ff9999"]

        fig, ax = plt.subplots(figsize=(5, 5))
        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            autopct="%1.1f%%",
            startangle=90,
            colors=colors,
            textprops={"color": "black", "fontsize": 11},
        )
        ax.set_title("SLA Compliance Across Transactions", fontsize=13)
        st.pyplot(fig)

    # ---------------- Error Matrix ----------------
    if error_rows:
        st.header("🧩 Error Matrix")
        df_error_matrix = pd.concat(error_rows, ignore_index=True)
        st.dataframe(df_error_matrix, use_container_width=True)
    else:
        st.warning("⚠️ No Top Errors section found — check report structure or encoding differences.")

else:
    st.info("👆 Please upload one or more StresStimulus HTML reports to compare.")
