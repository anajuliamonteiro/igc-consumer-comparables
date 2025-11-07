import streamlit as st
import pandas as pd

def render(df_buyers, df_macro_labels, df_micro_labels, conn):

    #Test

    df_buyers_display = df_buyers[["id", "mi_key", "entity", "website", "ticker", "macros", "micros", "country", "description", "ciq_industry", "ciq_industry_category"]]
    
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
        edited = st.data_editor(
            df_view,
            key="buyers_edit",
            column_config=config,
            hide_index=True,
        )

        # ---------- FAST BATCH AUTOSAVE ----------
        import time
        from itertools import chain

        def _as_list(x):
            if isinstance(x, list): return x
            if x is None: return []
            s = str(x).strip()
            if s.startswith("[") and s.endswith("]"):
                return [t.strip(" '\"") for t in s.strip("[]").split(",") if t.strip()]
            return [t.strip() for t in s.split(",") if t.strip()]

        key_col = "entity_id" if "entity_id" in edited.columns else "id"
        if {"micros", key_col}.issubset(edited.columns):

            # Build current UI snapshot
            ui_by_id = {
                str(row[key_col]): _as_list(row["micros"])
                for _, row in edited.iterrows()
            }

            # Debounce: only save at most once every 1.0s
            now = time.time()
            last_ts = st.session_state.get("last_fast_sync_ts", 0.0)
            changed_since_last = (
                st.session_state.get("last_synced_micros") is None or
                any(sorted(ui_by_id.get(k, [])) != st.session_state.get("last_synced_micros", {}).get(k, [])
                    for k in ui_by_id)
            )

            if changed_since_last and (now - last_ts) > 1.0:  # adjust window if needed
                try:
                    # 1) Collect ALL labels used across changed buyers
                    #    (compare vs last saved to limit the set)
                    prev = st.session_state.get("last_synced_micros", {})
                    changed_ids = [bid for bid in ui_by_id if prev.get(bid) != sorted(ui_by_id[bid])]
                    if not changed_ids:
                        st.session_state["last_fast_sync_ts"] = now
                        st.session_state["last_synced_micros"] = {k: sorted(v) for k, v in ui_by_id.items()}
                        st.stop()

                    labels_needed = sorted({
                        lab for lab in chain.from_iterable(ui_by_id[bid] for bid in changed_ids) if lab
                    })

                    # 2) Upsert new labels in ONE call
                    if labels_needed:
                        conn.table("micros").upsert(
                            [{"label": l} for l in labels_needed],
                            on_conflict="label"
                        ).execute()

                    # 3) Fetch all their IDs in ONE call
                    micro_rows = conn.table("micros").select("id,label").in_("label", labels_needed).execute().data or []
                    label_to_id = {r["label"]: r["id"] for r in micro_rows}

                    # 4) Fetch existing links for ALL changed buyers in ONE call
                    links = conn.table("buyer_micro_context") \
                        .select("entity_id,micro_id") \
                        .in_("entity_id", changed_ids) \
                        .execute().data or []

                    current_by_buyer = {}
                    for r in links:
                        current_by_buyer.setdefault(str(r["entity_id"]), set()).add(r["micro_id"])

                    # 5) Build desired sets and compute bulk add/delete
                    to_insert = []
                    to_delete_map = {}  # buyer_id -> set(micro_id)
                    for bid in changed_ids:
                        desired_ids = {label_to_id[l] for l in ui_by_id[bid] if l in label_to_id}
                        current_ids = current_by_buyer.get(bid, set())
                        add_ids = desired_ids - current_ids
                        del_ids = current_ids - desired_ids
                        if add_ids:
                            to_insert.extend([{"entity_id": bid, "micro_id": mid} for mid in add_ids])
                        if del_ids:
                            to_delete_map[bid] = del_ids

                    # 6) Apply bulk changes (ONE insert, ONE delete)
                    if to_insert:
                        conn.table("buyer_micro_context").insert(to_insert).execute()

                    # Delete by buyer in chunks
                    if to_delete_map:
                        # PostgREST needs one filter set; do per-buyer delete to keep it simple but still batched
                        for bid, mids in to_delete_map.items():
                            conn.table("buyer_micro_context") \
                                .delete() \
                                .eq("entity_id", bid) \
                                .in_("micro_id", list(mids)) \
                                .execute()

                    # 7) Update local snapshot (no rerun)
                    st.session_state["last_fast_sync_ts"] = now
                    st.session_state["last_synced_micros"] = {k: sorted(v) for k, v in ui_by_id.items()}
                    st.toast(f"Synced {len(changed_ids)} row(s).", icon="💾")

                except Exception as e:
                    st.error(getattr(e, "message", None) or str(e) or "Fast sync failed.")


    uploaded_file = st.file_uploader("Upload Buyers")
    