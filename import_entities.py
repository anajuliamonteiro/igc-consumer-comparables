import pandas as pd
import streamlit as st

def chunk_list(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]

def buyers_file(conn):
    uploaded_file = st.file_uploader(
        "Upload Buyers (CSV or Excel)",
        type=["csv", "xlsx", "xls", "xlsm"],
        key="buyers_file",
    )

    if not uploaded_file:
        return

    # --- 1) Read file ---
    try:
        name = uploaded_file.name.lower()
        if name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Could not read file: {e}")
        return

    # Normalize column names
    df.columns = [str(c).strip().lower() for c in df.columns]

    required_cols = ["entity", "mi_key", "ticker"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        st.error(f"Missing required columns in file: {', '.join(missing)}")
        return

    st.write("Preview of uploaded data:")
    st.dataframe(df.head())

    if st.button("Import into Supabase", type="primary", use_container_width=True):
        # --- 2) Build rows list ---
        rows = []
        for _, r in df.iterrows():
            entity = str(r["entity"]).strip() if pd.notna(r["entity"]) else None
            ticker = str(r["ticker"]).strip() if pd.notna(r["ticker"]) else None

            mi_val = r["mi_key"]
            if pd.isna(mi_val):
                mi_key = None
            else:
                try:
                    mi_key = int(float(mi_val))
                except Exception:
                    mi_key = None

            if not entity or mi_key is None or not ticker:
                continue

            row_data = {
                "entity": entity,
                "mi_key": mi_key,
                "ticker": ticker,
                "website": str(r.get("website") or "").strip() or None,
                "description": str(r.get("description") or "").strip() or None,
                "country": str(r.get("country") or "").strip() or None,
                "city": str(r.get("city") or "").strip() or None,
                "industry": str(r.get("industry") or "").strip() or None,
                "all_industries": str(r.get("all_industries") or "").strip() or None,
            }
            rows.append(row_data)

        if not rows:
            st.warning("No valid rows to insert.")
            return

        # --- 3) Deduplicate by mi_key (and optionally other keys) ---
        # Keep the last occurrence of each mi_key in the file
        df_rows = pd.DataFrame(rows)

        # Optional: also require (mi_key, entity, ticker) to be unique together
        # df_rows = df_rows.drop_duplicates(subset=["mi_key", "entity", "ticker"], keep="last")

        # Minimum: unique by mi_key
        df_rows = df_rows.drop_duplicates(subset=["mi_key"], keep="last")

        rows = df_rows.to_dict(orient="records")

        st.write("Number of rows after deduplication:", len(rows))

        # --- 4) Insert in chunks with upsert ---
        errors = []
        inserted_total = 0

        with st.spinner("Importing data into Supabase..."):
            for batch in chunk_list(rows, 500):
                try:
                    res = (
                        conn.table("entities")
                        .upsert(batch, on_conflict="mi_key")
                        .execute()
                    )
                    inserted_total += len(res.data or [])
                except Exception as e:
                    errors.append(str(e))

        if errors:
            st.error("Some errors occurred during import:")
            for e in errors:
                st.write(f"- {e}")
        else:
            st.success(f"Successfully imported (inserted/updated) {inserted_total} entities.")
