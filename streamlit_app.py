import os, streamlit as st
import pandas as pd
import altair as alt
from numpy.random import default_rng as rng
from st_supabase_connection import SupabaseConnection
from supabase import create_client
from gotrue.errors import AuthApiError
from views import buyers

st.set_page_config(page_title="Igc Consumer", page_icon="🧴", layout="wide", initial_sidebar_state="expanded")
alt.themes.enable("dark")

# Initialize connection.
conn = st.connection("supabase",type=SupabaseConnection)
# --------------

@st.cache_resource
def supabase_client():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except KeyError as e:
        st.error(f"Missing secret {e}. Add SUPABASE_URL and SUPABASE_KEY in app Secrets.")
        st.stop()
    return create_client(url, key)

sb = supabase_client()

if "session" not in st.session_state:
    st.session_state.session = sb.auth.get_session()
if "logged_in" not in st.session_state:
    st.session_state.logged_in = bool(st.session_state.session and st.session_state.session.user)

def sign_in(email: str, password: str):
    try:
        res = sb.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.session = res.session
        st.session_state.logged_in = True
        st.rerun()
    except AuthApiError as e:
        st.error(e.message or "Sign in failed")

def sign_up(email: str, password: str):
    try:
        sb.auth.sign_up({"email": email, "password": password})
        st.info("Check your email to confirm, then sign in.")
    except AuthApiError as e:
        st.error(e.message or "Sign up failed")

def sign_out():
    sb.auth.sign_out()
    st.session_state.session = None
    st.session_state.logged_in = False
    st.rerun()

def login_page():
    st.title("Login")
    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        go = st.form_submit_button("Sign in")
        if go:
            sign_in(email, password)

    with st.expander("Create an account"):
        e2 = st.text_input("New email")
        p2 = st.text_input("New password", type="password")
        if st.button("Sign up"):
            sign_up(e2, p2)

def main():
    user = st.session_state.session.user
    with st.sidebar:
        st.link_button("Go to Sharepoint", "https://igcpglobal.sharepoint.com/sites/plannercelulacr/Lists/Buyer%20Clula%20CR/AllItems.aspx?noAuthRedirect=1", width="stretch")
        st.link_button("Go to Loop", "https://igcpglobal.sharepoint.com/sites/plannercelulacr/Lists/Buyer%20Clula%20CR/AllItems.aspx?noAuthRedirect=1", width="stretch", icon="🚨")
        st.caption(f"Signed in as {user.email}")
        if st.button("Sign out"):
            sign_out()

        # entities_with_micros 
    res_micro = conn.table("entities_context").select("*").execute()
    df_micro = pd.DataFrame(res_micro.data or [])

    # Buyers Table
    res_buyers = conn.table("buyers_table").select("*").execute()
    df_buyers = pd.DataFrame(res_buyers.data or [])

    res_macro_labels = conn.table("macros").select("*").execute()
    df_macro_labels = pd.DataFrame(res_macro_labels.data or [])

    res_micro_labels = conn.table("micros").select("*").execute()
    df_micro_labels = pd.DataFrame(res_micro_labels.data or [])
    # Perform queries.
    res = conn.table("entities").select("*").execute()
    df = res.data

    res = conn.table("public").select("*").execute()
    public = res.data
    # --------------

    # Create DataFrame
    df = pd.DataFrame(
        df
    )

    public = pd.DataFrame(
        public
    )
    # --------------

    st.title("Igc Consumer & Retail")
    tab1, tab2, tab3, tab4 = st.tabs(["Buyers", "Adding Records", "Database Entities", "Trading [Undone]"])
    # --------------

    with tab4: 
        col = st.columns((6.5, 1.5), gap='medium')

        with col [0]:
            st.badge("19-09-2025", color="green")    
            entities = st.dataframe(
                df_micro[["entity", "website", "description", "ticker", "country", "city", "micros", "ciq_industry", "ciq_industry_category"]],
                key="entities",
                on_select="rerun",
                selection_mode=["multi-row", "multi-column"],
                column_config={
                    "website": st.column_config.LinkColumn(
                        "Website",
                    ),
                    "micros": st.column_config.ListColumn(
                        "Micros",
                        help="Example",
                        width="medium",
                    ),
                    "ciq_industry": st.column_config.ListColumn(
                        "CIQ Main Industry",
                        help="Example",
                        width="medium",
                    ),
                    "ciq_industry_category": st.column_config.ListColumn(
                        "CIQ Industries",
                        help="Example",
                        width="medium",
                    ),
                },
                hide_index=True,
            )

    with tab3: 
        col_tab2 = st.columns((6.5, 1.5), gap='medium')

        with col_tab2[1]:
                options = st.multiselect(
                    " ",
                    ["Wellness", "Beauty", "Education", "Food", "Statiorary"],
                )

        df_display = df_micro.drop(columns=[
                "id", "mi_key"
            ])

        with col_tab2[0]: 
            st.badge("19-09-2025", color="green")

            col_trading = st.columns((1, 1, 1, 1), gap='medium')

            median_ev_rev = df_display["EV_Revenue_LTM"].median()
            median_ev_ebitda = df_display["EV_EBITDA_LTM"].median()
            median_ev_rev_fwd = df_display["EV_Revenue_FWD"].median()
            median_ev_ebitda_fwd = df_display["EV_EBITDA_FWD"].median()
        
            with col_trading[0]:
                st.metric(label="**EV/Revenue (LTM)**", value=f"{median_ev_rev:,.2f}x", border=True, delta=0)

            with col_trading[1]:
                st.metric(label="**EV/EBITDA (LTM)**", value=f"{median_ev_ebitda:,.2f}x", delta=0, border=True)
            
            with col_trading[2]:
                st.metric(label="EV/Revenue (FWD)", value=f"{median_ev_rev_fwd:,.2f}x", delta=0, border=True)

            with col_trading[3]:
                st.metric(label="EV/EBITDA (FWD)", value=f"{median_ev_ebitda_fwd:,.2f}x", delta=0, border=True)

            trading = st.dataframe(
                df_display[[
                    "entity", "website", "ticker", "micros", "country", "description", "ciq_industry", "ciq_industry_category",
                    "EV_Revenue_LTM", "EV_Revenue_FWD", "Revenue_LTM",
                    "EV_EBITDA_LTM", "EV_EBITDA_FWD", "EBITDA_LTM", "EBITDA_Margin_LTM",
                    "Beta_5Y", "Enterprise_Value", "Market_Cap",
                    "CAGR_Revenue_5Y", "CAGR_Revenue_3Y",
                    "Gross_Profit_LTM", "Gross_Margin_LTM",
                    "CAGR_EBITDA_5Y", "CAGR_EBITDA_3Y",
                    "Net_Working_Capital", "Net_Working_Capital_Revenue",
                    "Average_Days_Inventory_Out_LTM", "Average_Days_Sales",
                    "price_change"
                ]],
                key="trading_",
                on_select="rerun",
                selection_mode=["multi-row", "multi-column"],
                column_config={
                    "website": st.column_config.LinkColumn(
                        "Website",
                    ),
                    "micros": st.column_config.ListColumn(
                        "Micros",
                        help="Example",
                        width="medium",
                    ),
                    "ciq_industry": st.column_config.ListColumn(
                        "CIQ Main Industry",
                        help="Example",
                        width="medium",
                    ),
                    "ciq_industry_category": st.column_config.ListColumn(
                        "CIQ Industries",
                        help="Example",
                        width="medium",
                    ),
                    "country": st.column_config.ListColumn(
                        "Country",
                        help="Example",
                    ),
                },
                hide_index=True,
            )

        with tab2:
            cols = st.columns((1.5, 4.5, 2), gap='medium')
            with cols[1]:
                with st.form("add_entity"):
                    entity = st.text_input("Entity name")
                    website = st.text_input("Website")
                    description = st.text_area("Description")
                    mi_key = st.number_input("MI Key", step=1)
                    ticker = st.text_input("Ticker", value="Private")
                    country = st.text_input("Country")
                    city = st.text_input("City")
                    industry = st.text_input("Industry")
                    all_industries = st.text_input("All Industries")
                    submitted = st.form_submit_button("Add Entity")

                    if submitted:
                        data = {
                            "entity": entity,
                            "website": website,
                            "description": description,
                            "mi_key": int(mi_key),
                            "ticker": ticker,
                            "country": country,
                            "city": city,
                            "industry": industry,
                            "all_industries": all_industries,
                        }

                        response = conn.table("entities").insert(data).execute()

        with tab1:
            buyers.render(df_buyers, df_macro_labels, df_micro_labels)

    # event.selection

if st.session_state.logged_in:
    main()
else:
    login_page()