"""Basic Streamlit frontend for Chicago Crime Analytics (talks to Flask API)."""

import os

import matplotlib.pyplot as plt
import pandas as pd
import requests
import seaborn as sns
import streamlit as st

API_URL = os.environ.get("FLASK_API_URL", "http://127.0.0.1:5000")

st.set_page_config(page_title="Chicago Crime Analytics", layout="wide")
st.title("Chicago Police Department — Crime Analytics")
st.caption("Simple Flask + SQLite3 + Streamlit Capstone Dashboard")

page = st.sidebar.radio("Navigation", ["Dashboard & Analytics", "Community CRUD", "Ask AI"])


def fetch_json(path: str, params: dict | None = None):
    """Helper to call GET endpoints on the Flask backend."""
    try:
        resp = requests.get(f"{API_URL}{path}", params=params, timeout=10)
        resp.raise_for_status()
        return resp.json(), None
    except requests.exceptions.ConnectionError:
        return None, (
            f"Cannot connect to Flask API at {API_URL}. "
            "Start it first with: `python app.py`"
        )
    except Exception as exc:
        return None, str(exc)


if page == "Dashboard & Analytics":
    data, error = fetch_json("/api/dashboard")
    if error:
        st.error(error)
        st.stop()

    kpis = data["kpis"]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Crimes", f"{kpis['total_crimes']:,}")
    col2.metric("Overall Arrest Rate", f"{kpis['arrest_rate']}%")
    col3.metric("Top Crime Type", kpis["top_crime_type"])
    col4.metric("Top Community Area", kpis["top_community"])

    st.subheader("Key Insights")
    for item in data["insights"]:
        st.write(f"- {item}")

    # Export PNG Report button
    try:
        png_resp = requests.get(f"{API_URL}/api/dashboard/export", timeout=15)
        if png_resp.status_code == 200:
            st.download_button(
                label="Download PNG Summary Report",
                data=png_resp.content,
                file_name="chicago_crime_dashboard_report.png",
                mime="image/png",
            )
    except Exception:
        pass

    st.divider()

    yearly_df = pd.DataFrame(data["yearly"])
    cat_df = pd.DataFrame(data["top_categories"])
    comm_df = pd.DataFrame(data["top_communities"])
    heat_df = pd.DataFrame(data["monthly_weekday"])

    left, right = st.columns(2)

    with left:
        st.subheader("1. Crime Trend Over Years")
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(yearly_df["Year"], yearly_df["crime_count"], marker="o", color="#1d4ed8")
        ax.set_xlabel("Year")
        ax.set_ylabel("Crime Count")
        ax.grid(True, alpha=0.3)
        st.pyplot(fig)
        plt.close(fig)

    with right:
        st.subheader("2. Top 10 Crime Categories")
        fig, ax = plt.subplots(figsize=(6, 4))
        ordered_cat = cat_df.sort_values("crime_count", ascending=True)
        ax.barh(ordered_cat["primary_type"], ordered_cat["crime_count"], color="#0f766e")
        ax.set_xlabel("Crime Count")
        st.pyplot(fig)
        plt.close(fig)

    left2, right2 = st.columns(2)

    with left2:
        st.subheader("3. Arrest Rate (%) by Year")
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(yearly_df["Year"].astype(str), yearly_df["arrest_rate"], color="#d97706")
        ax.set_xlabel("Year")
        ax.set_ylabel("Arrest Rate (%)")
        st.pyplot(fig)
        plt.close(fig)

    with right2:
        st.subheader("4. Top 10 Community Areas")
        fig, ax = plt.subplots(figsize=(6, 4))
        ordered_comm = comm_df.sort_values("crime_count", ascending=True)
        ax.barh(ordered_comm["community_name"], ordered_comm["crime_count"], color="#be123c")
        ax.set_xlabel("Crime Count")
        st.pyplot(fig)
        plt.close(fig)

    st.subheader("5. Heatmap: Crime Frequency by Month and Day of Week")
    if not heat_df.empty:
        day_order = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        pivot = heat_df.pivot(index="DayOfWeek", columns="Month", values="crime_count").fillna(0)
        pivot = pivot.reindex([d for d in day_order if d in pivot.index])
        fig, ax = plt.subplots(figsize=(10, 4))
        sns.heatmap(pivot, annot=True, fmt=".0f", cmap="YlOrRd", ax=ax)
        ax.set_xlabel("Month")
        ax.set_ylabel("Day of Week")
        st.pyplot(fig)
        plt.close(fig)

    st.divider()
    t1, t2 = st.columns(2)
    with t1:
        st.subheader("SQL View: vw_crime_yearly")
        st.dataframe(yearly_df, use_container_width=True)
    with t2:
        st.subheader("SQL View: vw_crime_by_category (Top 10)")
        st.dataframe(cat_df, use_container_width=True)

elif page == "Community CRUD":
    st.subheader("Community Dimension Table — CRUD (POST, PUT, PATCH, DELETE)")

    action = st.radio(
        "Select CRUD Operation",
        [
            "Create (POST)",
            "Read / Search (GET)",
            "Full Update (PUT)",
            "Partial Update (PATCH)",
            "Delete (DELETE)",
            "Crime Summary (GET)",
        ],
        horizontal=True,
    )

    st.divider()

    if action == "Read / Search (GET)":
        col_s, col_b = st.columns([4, 1])
        with col_s:
            search = st.text_input("Search by community code (exact match)", "")
        with col_b:
            st.write("")
            st.write("")
            refresh = st.button("Search / Refresh", use_container_width=True)

        if refresh or True:
            communities, error = fetch_json(
                "/api/community", params={"search": search} if search.strip() else None
            )
            if error:
                st.error(error)
                st.stop()
            st.write(f"Showing **{len(communities)}** community areas")
            st.dataframe(pd.DataFrame(communities), use_container_width=True)

    elif action == "Create (POST)":
        with st.form("create_form"):
            c_code = st.number_input("Community Code", min_value=1, step=1, value=99)
            c_name = st.text_input("Community Name", "")
            c_pop = st.number_input("Population", min_value=0, step=100, value=10000)
            c_area_mi = st.number_input("Area (sq mile)", min_value=0.0, value=2.5)
            c_area_km = st.number_input("Area (sq km)", min_value=0.0, value=6.47)
            c_dens_mi = st.number_input("Density (per sq mi)", min_value=0.0, value=4000.0)
            c_dens_km = st.number_input("Density (per sq km)", min_value=0.0, value=1545.0)
            submitted = st.form_submit_button("Create Community (POST)")
            if submitted:
                payload = {
                    "community_code": int(c_code),
                    "community_name": c_name,
                    "population": int(c_pop),
                    "area_sqmile": float(c_area_mi),
                    "area_sqkm": float(c_area_km),
                    "density_per_sqmi": float(c_dens_mi),
                    "density_per_sqkm": float(c_dens_km),
                }
                resp = requests.post(f"{API_URL}/api/community", json=payload, timeout=10)
                st.write(f"Status: **{resp.status_code}**")
                st.json(resp.json())

    elif action == "Full Update (PUT)":
        with st.form("put_form"):
            u_code = st.number_input("Community Code to Replace", min_value=1, step=1, value=99)
            u_name = st.text_input("New Community Name", "")
            u_pop = st.number_input("Population", min_value=0, step=100, value=15000)
            u_area_mi = st.number_input("Area (sq mile)", min_value=0.0, value=3.0)
            u_area_km = st.number_input("Area (sq km)", min_value=0.0, value=7.77)
            u_dens_mi = st.number_input("Density (per sq mi)", min_value=0.0, value=5000.0)
            u_dens_km = st.number_input("Density (per sq km)", min_value=0.0, value=1930.0)
            submitted = st.form_submit_button("Replace Community (PUT)")
            if submitted:
                payload = {
                    "community_name": u_name,
                    "population": int(u_pop),
                    "area_sqmile": float(u_area_mi),
                    "area_sqkm": float(u_area_km),
                    "density_per_sqmi": float(u_dens_mi),
                    "density_per_sqkm": float(u_dens_km),
                }
                resp = requests.put(
                    f"{API_URL}/api/community/{int(u_code)}", json=payload, timeout=10
                )
                st.write(f"Status: **{resp.status_code}**")
                st.json(resp.json())

    elif action == "Partial Update (PATCH)":
        with st.form("patch_form"):
            p_code = st.number_input("Community Code to Patch", min_value=1, step=1, value=99)
            p_name = st.text_input("Community Name (leave blank to skip)", "")
            p_pop = st.text_input("Population (leave blank to skip)", "")
            submitted = st.form_submit_button("Partial Update (PATCH)")
            if submitted:
                payload = {}
                if p_name.strip():
                    payload["community_name"] = p_name.strip()
                if p_pop.strip():
                    payload["population"] = int(p_pop.strip())
                resp = requests.patch(
                    f"{API_URL}/api/community/{int(p_code)}", json=payload, timeout=10
                )
                st.write(f"Status: **{resp.status_code}**")
                st.json(resp.json())

    elif action == "Delete (DELETE)":
        with st.form("delete_form"):
            d_code = st.number_input("Community Code to Delete", min_value=1, step=1, value=99)
            submitted = st.form_submit_button("Delete Community (DELETE)")
            if submitted:
                resp = requests.delete(
                    f"{API_URL}/api/community/{int(d_code)}", timeout=10
                )
                st.write(f"Status: **{resp.status_code}**")
                st.json(resp.json())

    else:
        s_code = st.number_input("Community Code", min_value=1, step=1, value=25)
        if st.button("Get Crime Summary"):
            resp = requests.get(
                f"{API_URL}/api/community/{int(s_code)}/crime-summary", timeout=10
            )
            st.write(f"Status: **{resp.status_code}**")
            st.json(resp.json())

else:
    st.subheader("Ask AI — Natural Language to SQL (Groq / gpt-oss)")
    st.caption("Ask any question about Chicago crimes, arrests, or communities. Groq generates a SQL query, runs it on SQLite, and summarizes the answer.")

    groq_key = st.sidebar.text_input(
        "Groq API Key (optional if GROQ_API_KEY is set)",
        type="password",
    )

    if "ai_chat" not in st.session_state:
        st.session_state.ai_chat = []

    for msg in st.session_state.ai_chat:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if msg.get("sql"):
                with st.expander("Generated SQL & Results"):
                    st.code(msg["sql"], language="sql")
                    if msg.get("rows"):
                        st.dataframe(pd.DataFrame(msg["rows"]), use_container_width=True)

    prompt = st.chat_input("e.g. Which are the top 5 crime types in 2016?")
    if prompt:
        st.session_state.ai_chat.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Generating SQL and querying SQLite..."):
                try:
                    resp = requests.post(
                        f"{API_URL}/api/ask-ai",
                        json={"question": prompt, "api_key": groq_key},
                        timeout=45,
                    )
                    payload = resp.json()
                    if resp.status_code == 200 and payload.get("answer"):
                        answer = payload["answer"]
                        st.write(answer)
                        with st.expander("Generated SQL & Results"):
                            st.code(payload.get("sql", ""), language="sql")
                            if payload.get("rows"):
                                st.dataframe(pd.DataFrame(payload["rows"]), use_container_width=True)
                        st.session_state.ai_chat.append(
                            {
                                "role": "assistant",
                                "content": answer,
                                "sql": payload.get("sql"),
                                "rows": payload.get("rows"),
                            }
                        )
                    else:
                        err = payload.get("error", "Unknown error")
                        st.error(err)
                        if payload.get("sql"):
                            st.code(payload["sql"], language="sql")
                        st.session_state.ai_chat.append({"role": "assistant", "content": err})
                except requests.exceptions.ConnectionError:
                    err = f"Cannot connect to Flask API at {API_URL}. Start it first with: `python run.py`"
                    st.error(err)
                    st.session_state.ai_chat.append({"role": "assistant", "content": err})
