import streamlit as st
import pandas as pd

def render(df_buyers, df_macro_labels, df_micro_labels):
    # col = st.columns((6.5, 1.5), gap='medium')

    # with col[0]:

    df_buyers_display = df_buyers[["entity", "website", "ticker", "macros", "micros", "country", "description", "ciq_industry", "ciq_industry_category"]]
    
    macro_labels = df_macro_labels["label"].dropna().astype(str).tolist()
    micro_labels = df_micro_labels["label"].dropna().astype(str).tolist()
    countries_labels = df_buyers["country"].dropna().unique().astype(str).tolist()
    industries_labels = sorted(pd.Series(df_buyers["ciq_industry_category"]).dropna().apply(lambda x: x if isinstance(x, list) else [x]).explode().astype(str).str.strip().replace({"", "nan", "none", "null"}, pd.NA).dropna().drop_duplicates().tolist())
    industry_labels = sorted(pd.Series(df_buyers["ciq_industry"]).dropna().apply(lambda x: x if isinstance(x, list) else [x]).explode().astype(str).str.strip().replace({"", "nan", "none", "null"}, pd.NA).dropna().drop_duplicates().tolist())
    
    col_filter = st.columns((1, 1, 1, 1, 1, 1), gap='medium')
    with col_filter[1]:
        macros = st.multiselect("Macro", macro_labels)

    with col_filter[2]:
        micros = st.multiselect("Micro", micro_labels)

    with col_filter[3]:
        countries = st.multiselect("Country", countries_labels)

    with col_filter[4]:
        industry = st.multiselect("Industry", industry_labels)

    with col_filter[5]:
        industries = st.multiselect("Industries", industries_labels)

    with col_filter[0]: 
        selection = st.segmented_control("Buyers' Database", ['View','Edit'], label_visibility="hidden", selection_mode="single", default='View')


    to_set = lambda v: (set(map(lambda x: str(x).strip(), v)) if isinstance(v, list)
                        else ({str(v).strip()} if pd.notna(v) else set()))
    mask = pd.Series(True, index=df_buyers_display.index)
    if macros:    mask &= df_buyers_display["macros"].apply(lambda v: bool(to_set(v) & set(map(str, macros))))
    if micros:    mask &= df_buyers_display["micros"].apply(lambda v: bool(to_set(v) & set(map(str, micros))))
    if countries: mask &= df_buyers_display["country"].apply(lambda v: bool(to_set(v) & set(map(str, countries))))
    if industry:  mask &= df_buyers_display["ciq_industry"].apply(lambda v: bool(to_set(v) & set(map(str, industry))))
    if industries:mask &= df_buyers_display["ciq_industry_category"].apply(lambda v: bool(to_set(v) & set(map(str, industries))))
    df_view = df_buyers_display[mask]
    
    config = {
        "website": st.column_config.LinkColumn(
                    "Website",
                ),
                "macros": st.column_config.MultiselectColumn(
                    "Macros", 
                    help="Example",
                    width="medium",
                    options=macro_labels,
                    color=["#404040"],
                ),
                "micros": st.column_config.MultiselectColumn(
                    "Micros", 
                    help="Example",
                    width="medium",
                    options=micro_labels,
                    color=["#404040"],
                ),
                "ciq_industry": st.column_config.ListColumn(
                    "Main Industry",
                    help="Example",
                    width="medium",
                ),
                "ciq_industry_category": st.column_config.ListColumn(
                    "Industries",
                    help="Example",
                    width="medium",
                ),
                "country": st.column_config.ListColumn(
                    "Country",
                    help="Example",
                ),
    }

    if selection == 'View':
        st.dataframe(
            df_view,
            key="buyers_view",
            on_select="rerun",
            selection_mode=["multi-row", "multi-column"],
            column_config=config,
            hide_index=True,
        )
        
    elif selection == 'Edit':
        st.data_editor(
            df_view,
            key="buyers_edit",
            column_config=config,
            hide_index=True,
        )

    uploaded_file = st.file_uploader("Upload Buyers")
    