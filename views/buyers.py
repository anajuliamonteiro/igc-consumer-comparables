import streamlit as st
import pandas as pd
import datetime
import import_entities


def render(df_buyers, df_macro_labels, df_micro_labels, conn):

    # Keep id for internal use, drop mi_key; order intel columns after micros
    df_buyers_display = df_buyers[
        [
            "id",  # kept for internal logic, hidden from the UI
            "entity",
            "website",
            "ticker",
            "macros",
            "micros",
            "intel",
            "intel_date",
            "country",
            "description",
            "ciq_industry",
            "ciq_industry_category",
        ]
    ]

    @st.cache_data(ttl=300)
    def _labels(macro_df, micro_df, df_buyers):
        return (
            macro_df["label"].dropna().astype(str).tolist(),
            micro_df["label"].dropna().astype(str).tolist(),
            df_buyers["country"].dropna().unique().astype(str).tolist(),
            sorted(
                pd.Series(df_buyers["ciq_industry_category"])
                .dropna()
                .apply(lambda x: x if isinstance(x, list) else [x])
                .explode()
                .astype(str)
                .str.strip()
                .replace({"", "nan", "none", "null"}, pd.NA)
                .dropna()
                .drop_duplicates()
                .tolist()
            ),
            sorted(
                pd.Series(df_buyers["ciq_industry"])
                .dropna()
                .apply(lambda x: x if isinstance(x, list) else [x])
                .explode()
                .astype(str)
                .str.strip()
                .replace({"", "nan", "none", "null"}, pd.NA)
                .dropna()
                .drop_duplicates()
                .tolist()
            ),
        )

    macro_labels, micro_labels, countries_labels, industries_labels, industry_labels = _labels(
        df_macro_labels, df_micro_labels, df_buyers
    )

    col_filter = st.columns((1, 1, 1, 1, 1, 1), gap="medium")
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
        selection = st.segmented_control(
            "Buyers' Database",
            ["View", "Edit"],
            label_visibility="hidden",
            selection_mode="single",
            default="Edit",
        )

    to_set = (
        lambda v: (
            set(map(lambda x: str(x).strip(), v))
            if isinstance(v, list)
            else ({str(v).strip()} if pd.notna(v) else set())
        )
    )
    mask = pd.Series(True, index=df_buyers_display.index)
    if macros:
        mask &= df_buyers_display["macros"].apply(
            lambda v: bool(to_set(v) & set(map(str, macros)))
        )
    if micros:
        mask &= df_buyers_display["micros"].apply(
            lambda v: bool(to_set(v) & set(map(str, micros)))
        )
    if countries:
        mask &= df_buyers_display["country"].apply(
            lambda v: bool(to_set(v) & set(map(str, countries)))
        )
    if industry:
        mask &= df_buyers_display["ciq_industry"].apply(
            lambda v: bool(to_set(v) & set(map(str, industry)))
        )
    if industries:
        mask &= df_buyers_display["ciq_industry_category"].apply(
            lambda v: bool(to_set(v) & set(map(str, industries)))
        )

    # df_view keeps id internally; we will hide it in the UI
    df_view = df_buyers_display[mask].copy()

    # Ensure intel_date is a proper date so DateColumn is compatible
    if "intel_date" in df_view.columns:
        df_view["intel_date"] = pd.to_datetime(
            df_view["intel_date"], errors="coerce"
        ).dt.date

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
        "intel": st.column_config.Column(
            "Intel",
            help="Internal intel notes",
            width="large",  # bigger
        ),
        "intel_date": st.column_config.DateColumn(
            "Intel Date",
            width="medium",  # bigger; use "large" or "300px" if you want
            format="YYYY-MM-DD",
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

    # We hide "id" from the displayed dataframes/editors
    df_view_display = df_view.drop(columns=["id"])

    if selection == "View":
        st.dataframe(
            df_view_display,
            key="buyers_view",
            on_select="rerun",
            selection_mode=["multi-row", "multi-column"],
            column_config=config,
            hide_index=True,
        )

    elif selection == "Edit":
        edited = st.data_editor(
            df_view_display,
            key="buyers_edit",
            column_config=config,
            hide_index=True,
        )

        # ---------- FAST BATCH AUTOSAVE ----------
        import time
        from itertools import chain

        def _as_list(x):
            if isinstance(x, list):
                return x
            if x is None:
                return []
            s = str(x).strip()
            if s.startswith("[") and s.endswith("]"):
                return [
                    t.strip(" '\"")
                    for t in s.strip("[]").split(",")
                    if t.strip()
                ]
            return [t.strip() for t in s.split(",") if t.strip()]

        # We no longer rely on an "id" column in `edited` (it's hidden),
        # we map by index back to df_view to get the real entity id.
        if "micros" in edited.columns and "id" in df_view.columns:

            # Build current UI snapshot: buyer_id -> list of micros
            ui_by_id = {
                str(df_view.loc[idx, "id"]): _as_list(row["micros"])
                for idx, row in edited.iterrows()
            }

            # Debounce: only save at most once every 1.0s
            now = time.time()
            last_ts = st.session_state.get("last_fast_sync_ts", 0.0)
            changed_since_last = (
                st.session_state.get("last_synced_micros") is None
                or any(
                    sorted(ui_by_id.get(k, []))
                    != st.session_state.get(
                        "last_synced_micros", {}
                    ).get(k, [])
                    for k in ui_by_id
                )
            )

            if changed_since_last and (now - last_ts) > 1.0:  # adjust window if needed
                try:
                    # 1) Collect ALL labels used across changed buyers
                    prev = st.session_state.get("last_synced_micros", {})
                    changed_ids = [
                        bid
                        for bid in ui_by_id
                        if prev.get(bid) != sorted(ui_by_id[bid])
                    ]
                    if not changed_ids:
                        st.session_state["last_fast_sync_ts"] = now
                        st.session_state["last_synced_micros"] = {
                            k: sorted(v) for k, v in ui_by_id.items()
                        }
                        st.stop()

                    labels_needed = sorted(
                        {
                            lab
                            for lab in chain.from_iterable(
                                ui_by_id[bid] for bid in changed_ids
                            )
                            if lab
                        }
                    )

                    # 2) Upsert new labels in ONE call
                    if labels_needed:
                        conn.table("micros").upsert(
                            [{"label": l} for l in labels_needed],
                            on_conflict="label",
                        ).execute()

                    # 3) Fetch all their IDs in ONE call
                    micro_rows = (
                        conn.table("micros")
                        .select("id,label")
                        .in_("label", labels_needed)
                        .execute()
                        .data
                        or []
                    )
                    label_to_id = {r["label"]: r["id"] for r in micro_rows}

                    # 4) Fetch existing links for ALL changed buyers in ONE call
                    links = (
                        conn.table("buyer_micro_context")
                        .select("entity_id,micro_id")
                        .in_("entity_id", changed_ids)
                        .execute()
                        .data
                        or []
                    )

                    current_by_buyer = {}
                    for r in links:
                        current_by_buyer.setdefault(
                            str(r["entity_id"]), set()
                        ).add(r["micro_id"])

                    # 5) Build desired sets and compute bulk add/delete
                    to_insert = []
                    to_delete_map = {}  # buyer_id -> set(micro_id)
                    for bid in changed_ids:
                        desired_ids = {
                            label_to_id[l]
                            for l in ui_by_id[bid]
                            if l in label_to_id
                        }
                        current_ids = current_by_buyer.get(bid, set())
                        add_ids = desired_ids - current_ids
                        del_ids = current_ids - desired_ids
                        if add_ids:
                            to_insert.extend(
                                [
                                    {
                                        "entity_id": bid,
                                        "micro_id": mid,
                                    }
                                    for mid in add_ids
                                ]
                            )
                        if del_ids:
                            to_delete_map[bid] = del_ids

                    # 6) Apply bulk changes (ONE insert, ONE delete)
                    if to_insert:
                        conn.table("buyer_micro_context").insert(
                            to_insert
                        ).execute()

                    # Delete by buyer in chunks
                    if to_delete_map:
                        for bid, mids in to_delete_map.items():
                            (
                                conn.table("buyer_micro_context")
                                .delete()
                                .eq("entity_id", bid)
                                .in_("micro_id", list(mids))
                                .execute()
                            )

                    # 7) Update local snapshot (no rerun)
                    st.session_state["last_fast_sync_ts"] = now
                    st.session_state["last_synced_micros"] = {
                        k: sorted(v) for k, v in ui_by_id.items()
                    }
                    st.toast(
                        f"Synced {len(changed_ids)} row(s).", icon="💾"
                    )

                except Exception as e:
                    st.error(
                        getattr(e, "message", None)
                        or str(e)
                        or "Fast sync failed."
                    )

    # ----------------- BOTTOM ROW: FILE + INTEL PANEL -----------------
    cols = st.columns((1, 1), gap="medium")
    with cols[0]:
        import_entities.buyers_file(conn)

    # Intel date/text for a SPECIFIC selected entity (company)
    with cols[1]:
        selected_row = None
        selected_entity = None

        # We only support selection from the 'View' table,
        # since that's where you used on_select="rerun"
        view_state = st.session_state.get("buyers_view")

        if view_state and isinstance(view_state, dict):
            sel = view_state.get("selection", {})
            selected_rows = sel.get("rows", [])

            # Require at least one selected row; if multiple, take the first
            if selected_rows:
                row_idx = selected_rows[0]
                # df_view and df_view_display share the same index
                if 0 <= row_idx < len(df_view):
                    selected_row = df_view.iloc[row_idx]
                    selected_entity = selected_row.get("entity", None)

        # IMPORTANT: avoid ambiguous truth value for Series
        if selected_row is None:
            st.info("Select a single company in the **View** table to add or edit intel.")
        else:
            # current intel values
            current_intel = selected_row.get("intel", "") if "intel" in selected_row else ""
            current_intel_date = selected_row.get("intel_date", None) if "intel_date" in selected_row else None

            # normalize date for the widget:
            # - if it's a Timestamp, convert to date
            # - if it's NaT/NaN/None, use today as a safe default
            if isinstance(current_intel_date, pd.Timestamp):
                current_intel_date = current_intel_date.date()

            if pd.isna(current_intel_date):
                current_intel_date = datetime.date.today()

            st.badge(f"Intel for: {selected_entity or 'Selected Company'}")

            with st.form("intel_form"):
                intel_date = st.date_input(
                    "Intel Date",
                    value=current_intel_date,
                    key="intel_date",
                )
                intel_text = st.text_area(
                    "Intel",
                    value=current_intel or "",
                    key="intel_text",
                )
                col_btns = st.columns(5)
                with col_btns[0]:
                    save_clicked = st.form_submit_button("Save intel")
                with col_btns[1]:
                    clear_clicked = st.form_submit_button("Clear intel")

            entity_id = selected_row["id"]

            # SAVE flow
            if save_clicked:
                if not intel_date or not intel_text.strip():
                    st.warning("Please provide both an intel date and some text, or use 'Clear intel' to remove it.")
                else:
                    try:
                        conn.table("entities").update(
                            {
                                "intel_date": str(intel_date),
                                "intel": intel_text.strip(),
                            }
                        ).eq("id", entity_id).execute()
                        st.success("Intel saved.")
                    except Exception as e:
                        st.error(
                            "Could not save intel to the database. Showing captured data below."
                        )
                        st.write(
                            {
                                "entity_id": entity_id,
                                "intel_date": intel_date,
                                "intel_text": intel_text.strip(),
                                "error": str(e),
                            }
                        )

            # CLEAR flow
            if clear_clicked:
                try:
                    conn.table("entities").update(
                        {
                            "intel_date": None,
                            "intel": None,
                        }
                    ).eq("id", entity_id).execute()
                    st.success("Intel cleared.")
                except Exception as e:
                    st.error(
                        "Could not clear intel in the database. Showing captured data below."
                    )
                    st.write(
                        {
                            "entity_id": entity_id,
                            "error": str(e),
                        }
                    )