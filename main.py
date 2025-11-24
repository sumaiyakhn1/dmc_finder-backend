def load_excel_mappings():
    global college_to_exam

    files = [
        "data/mapping_1sem.xlsx",
        "data/mapping_3sem.xlsx",
        "data/mapping_5sem.xlsx",
    ]

    for file in files:
        print(f"[INIT] Loading mapping file: {file}")

        # ALWAYS load as string to avoid scientific notation
        df = pd.read_excel(file, dtype=str)

        # Clean all string values (strip spaces, remove .0, fix e+12)
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
        df = df.fillna("")

        def clean_num(val):
            if not isinstance(val, str):
                return ""
            val = val.replace(".0", "")      # remove float suffix
            if "e+" in val.lower():          # convert scientific notation
                try:
                    return str(int(float(val)))
                except:
                    return val
            return val

        # Apply number cleaning on all columns
        for c in df.columns:
            df[c] = df[c].apply(clean_num)

        df.columns = [c.strip() for c in df.columns]  # clean headers

        # Detect column names
        col_college = None
        col_exam = None

        for col in df.columns:
            if "roll" in col.lower() and "exam" not in col.lower():
                col_college = col
            if "exam" in col.lower():
                col_exam = col

        if not col_college or not col_exam:
            raise RuntimeError(f"Invalid mapping file: {file}")

        print(f"[INIT] {file} → Using College='{col_college}', Exam='{col_exam}'")

        # Build mapping dict
        for i, row in df.iterrows():
            college = row[col_college]
            exam = row[col_exam]

            if college.isdigit() and exam.isdigit():
                college_to_exam[college] = exam

    print(f"[DONE] Loaded {len(college_to_exam)} college→exam mappings")
