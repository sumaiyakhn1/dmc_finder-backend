from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
import csv
import os
from typing import Dict, List, Optional

# ========= CONFIG =========

DATA_DIR = "data"
DRIVE_INDEX_CSV = os.path.join(DATA_DIR, "drive_index.csv")

MAPPING_FILES: List[str] = [
    os.path.join(DATA_DIR, "mapping_1sem.xlsx"),
    os.path.join(DATA_DIR, "mapping_3sem.xlsx"),
    os.path.join(DATA_DIR, "mapping_5sem.xlsx"),
]

CSV_COL_FILE_NAME = "File Name"
CSV_COL_FILE_ID = "File ID"
CSV_COL_PATH = "Path"


# ========= IN-MEMORY INDEX =========

college_to_exam: Dict[str, str] = {}
exam_to_file: Dict[str, Dict[str, str]] = {}


# ========= FASTAPI APP =========

app = FastAPI(title="Admit Card Search API")


# ========= MODELS =========

class SearchRequest(BaseModel):
    roll_no: str


class SearchResponse(BaseModel):
    college_roll: str
    exam_roll: str
    file_name: str
    path: str
    drive_view_url: str
    drive_download_url: str
    note: Optional[str] = None


# ========= FUNCTIONS =========

def auto_detect_columns(df, filename):
    """
    Detect college roll column + exam roll column based on header keywords.
    Works with files like:
    - Roll No.
    - College Roll Number
    - Exam Roll No.
    - Exam Roll Number
    """
    cols = list(df.columns)
    lower_cols = [c.lower() for c in cols]

    # exam roll column: must contain "exam" and "roll"
    exam_idx = next(
        (i for i, c in enumerate(lower_cols) if "exam" in c and "roll" in c),
        None,
    )
    if exam_idx is None:
        raise RuntimeError(
            f"[ERROR] Could not detect Exam Roll column in file {filename}\n"
            f"Found columns: {cols}"
        )

    # college roll: 1) contains "college" + "roll"
    college_idx = next(
        (i for i, c in enumerate(lower_cols) if "college" in c and "roll" in c),
        None,
    )

    # fallback 2) any "roll" that is not the exam roll
    if college_idx is None:
        college_idx = next(
            (i for i, c in enumerate(lower_cols) if "roll" in c and i != exam_idx),
            None,
        )

    if college_idx is None:
        raise RuntimeError(
            f"[ERROR] Could not detect College Roll column in file {filename}\n"
            f"Found columns: {cols}"
        )

    return cols[college_idx], cols[exam_idx]


def load_excel_mappings():
    """Load all mappings: College Roll -> Exam Roll"""

    global college_to_exam
    college_to_exam = {}

    for path in MAPPING_FILES:
        if not os.path.exists(path):
            print(f"[WARN] Mapping file missing, skipping: {path}")
            continue

        print(f"[INIT] Loading mapping file: {path}")
        df = pd.read_excel(path, dtype=str, engine="openpyxl")

        college_col, exam_col = auto_detect_columns(df, path)

        print(
            f"[INIT] {os.path.basename(path)} → Using College='{college_col}', Exam='{exam_col}'"
        )

        for _, row in df.iterrows():
            college_roll = str(row[college_col]).strip()
            exam_roll = str(row[exam_col]).strip()

            if not college_roll or college_roll.lower() == "nan":
                continue
            if not exam_roll or exam_roll.lower() == "nan":
                continue

            college_to_exam[college_roll] = exam_roll

    print(f"[DONE] Loaded {len(college_to_exam)} college→exam mappings")


def load_drive_index():
    """Load exam_roll → file info from drive_index.csv"""

    global exam_to_file
    exam_to_file = {}

    if not os.path.exists(DRIVE_INDEX_CSV):
        raise RuntimeError(f"drive_index.csv missing at {DRIVE_INDEX_CSV}")

    print(f"[INIT] Loading drive index: {DRIVE_INDEX_CSV}")

    with open(DRIVE_INDEX_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            file_name = (row.get(CSV_COL_FILE_NAME) or "").strip()
            file_id = (row.get(CSV_COL_FILE_ID) or "").strip()
            path = (row.get(CSV_COL_PATH) or "").strip()

            if not file_name or not file_id:
                continue

            exam_roll = file_name.split("_")[0].split(".")[0]

            if exam_roll not in exam_to_file:
                exam_to_file[exam_roll] = {
                    "file_name": file_name,
                    "file_id": file_id,
                    "path": path,
                }

    print(f"[DONE] Loaded {len(exam_to_file)} exam→file mappings")


def build_indexes():
    print("\n==== BUILDING INDEXES ====")
    load_excel_mappings()
    load_drive_index()
    print("==== INDEX BUILD COMPLETE ====\n")


# ========= STARTUP =========

@app.on_event("startup")
def on_startup():
    build_indexes()


# ========= ENDPOINTS =========

@app.get("/health")
def health():
    return {
        "status": "ok",
        "mapping_count": len(college_to_exam),
        "file_count": len(exam_to_file),
    }


@app.post("/search", response_model=SearchResponse)
def search(payload: SearchRequest):
    roll = payload.roll_no.strip()

    if roll not in college_to_exam:
        raise HTTPException(404, "College Roll Number not found")

    exam_roll = college_to_exam[roll]

    if exam_roll not in exam_to_file:
        raise HTTPException(404, "PDF not found for this Exam Roll Number")

    file_info = exam_to_file[exam_roll]

    file_id = file_info["file_id"]
    drive_view = f"https://drive.google.com/file/d/{file_id}/view?usp=drivesdk"
    drive_down = f"https://drive.google.com/uc?export=download&id={file_id}"

    return SearchResponse(
        college_roll=roll,
        exam_roll=exam_roll,
        file_name=file_info["file_name"],
        path=file_info["path"],
        drive_view_url=drive_view,
        drive_download_url=drive_down,
    )
