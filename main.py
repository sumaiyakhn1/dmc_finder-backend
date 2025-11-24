import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

# =============================
# FASTAPI APP
# =============================
app = FastAPI()

# Allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================
# GLOBAL STORAGE
# =============================
college_to_exam = {}
exam_to_file = {}

# =============================
# SEARCH QUERY MODEL
# =============================
class SearchQuery(BaseModel):
    roll_no: str


# =============================
# LOAD EXCEL MAPPINGS (1 / 3 / 5 sem)
# =============================
def load_excel_mappings():
    global college_to_exam

    files = [
        "data/mapping_1sem.xlsx",
        "data/mapping_3sem.xlsx",
        "data/mapping_5sem.xlsx",
    ]

    for file in files:
        print(f"[INIT] Loading mapping file: {file}")

        # Load as string (prevents scientific notation)
        df = pd.read_excel(file, dtype=str)

        # Clean all values
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
        df = df.fillna("")

        # Clean number formatting
        def clean_num(val):
            if not isinstance(val, str):
                return ""
            val = val.replace(".0", "")
            if "e+" in val.lower():      # scientific notation
                try:
                    return str(int(float(val)))
                except:
                    return val
            return val

        # Apply cleaning
        for col in df.columns:
            df[col] = df[col].apply(clean_num)

        df.columns = [c.strip() for c in df.columns]

        # Detect column names
        col_college = None
        col_exam = None

        for col in df.columns:
            name = col.lower()
            if "roll" in name and "exam" not in name:
                col_college = col
            if "exam" in name:
                col_exam = col

        if not col_college or not col_exam:
            raise RuntimeError(f"Invalid mapping file: {file}")

        print(f"[INIT] {file} → Using College='{col_college}', Exam='{col_exam}'")

        # Build mapping dict
        for _, row in df.iterrows():
            college = row[col_college]
            exam = row[col_exam]

            if college.isdigit() and exam.isdigit():
                college_to_exam[college] = exam

    print(f"[DONE] Loaded {len(college_to_exam)} college→exam mappings")


# =============================
# LOAD DRIVE INDEX CSV
# =============================
def load_drive_index():
    global exam_to_file

    print("[INIT] Loading drive index: data/drive_index.csv")

    df = pd.read_csv("data/drive_index.csv")
    df.columns = [c.strip() for c in df.columns]

    required = ["File Name", "File ID", "Path"]
    for c in required:
        if c not in df.columns:
            raise RuntimeError("Drive index missing required columns")

    for _, row in df.iterrows():
        file_name = str(row["File Name"]).strip()
        file_id = str(row["File ID"]).strip()
        path = str(row["Path"]).strip()

        # Extract Exam Roll from filename
        if "_" in file_name:
            exam_roll = file_name.split("_")[0]
        else:
            exam_roll = file_name.split(".")[0]

        if exam_roll.isdigit():
            exam_to_file[exam_roll] = {
                "File Name": file_name,
                "File ID": file_id,
                "Path": path,
            }

    print(f"[DONE] Loaded {len(exam_to_file)} exam→file mappings")


# =============================
# STARTUP
# =============================
@app.on_event("startup")
def on_startup():
    print("==== BUILDING INDEXES ====")
    load_excel_mappings()
    load_drive_index()
    print("==== INDEX BUILD COMPLETE ====")


# =============================
# HELPER FUNCTION
# =============================
def build_result(exam_roll, college_roll=None):
    file = exam_to_file.get(exam_roll)

    if not file:
        raise HTTPException(status_code=404, detail="Exam Roll not found in drive")

    return {
        "college_roll": college_roll,
        "exam_roll": exam_roll,
        "file_name": file["File Name"],
        "path": file["Path"],
        "drive_view_url": f"https://drive.google.com/file/d/{file['File ID']}/view",
        "drive_download_url": f"https://drive.google.com/uc?export=download&id={file['File ID']}",
    }


# =============================
# MAIN SEARCH ENDPOINT
# =============================
@app.post("/search")
def search(query: SearchQuery):
    roll = query.roll_no.strip()

    # Try as college roll
    if roll in college_to_exam:
        exam_roll = college_to_exam[roll]
        return build_result(exam_roll, roll)

    # Try as exam roll
    if roll in exam_to_file:
        return build_result(roll)

    raise HTTPException(status_code=404, detail="Roll Number not found")


# =============================
# HEALTH CHECK
# =============================
@app.get("/health")
def health():
    return {
        "status": "ok",
        "mapping_count": len(college_to_exam),
        "file_count": len(exam_to_file),
    }
