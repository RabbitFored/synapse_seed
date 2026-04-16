import os
import shutil
from pathlib import Path
import re

source_dir = Path("data/pyq/TNMGRU/raw")
target_dir = Path("data/pyq/TNMGRU/processed/subjects")

SUBJECT_MAPPING = {
    # Anatomy
    "anatomy - i": ("Anatomy", "p1"),
    "anatomy - ii": ("Anatomy", "p2"),
    "anatomy - paper i": ("Anatomy", "p1"),
    "anatomy -paper ii": ("Anatomy", "p2"),
    "human anatomy - i": ("Anatomy", "p1"),
    "human anatomy - ii": ("Anatomy", "p2"),
    
    # Physiology
    "physiology - i": ("Physiology", "p1"),
    "physiology - ii": ("Physiology", "p2"),
    "physiology - i (old_new regulations)": ("Physiology", "p1"),
    "physiology - ii (old_new regulations)": ("Physiology", "p2"),
    "physiology -paper i": ("Physiology", "p1"),
    "physiology -paper ii": ("Physiology", "p2"),
    "physiology including biophysics - i": ("Physiology", "p1"),
    "physiology including biophysics - ii": ("Physiology", "p2"),
    
    # Biochemistry
    "biochemistry - i": ("Biochemistry", "p1"),
    "biochemistry - ii": ("Biochemistry", "p2"),
    "biochemistry - i (old_new regulations)": ("Biochemistry", "p1"),
    "biochemistry -paper i": ("Biochemistry", "p1"),
    "biochemistry -paper ii": ("Biochemistry", "p2"),
    
    # Pharmacology
    "pharmacology": ("Pharmacology", "p1_p2"),
    "pharmacology - i": ("Pharmacology", "p1"),
    "pharmacology- ii": ("Pharmacology", "p2"),
    "pharmacology - ii": ("Pharmacology", "p2"),

    # Pathology
    "pathology - i": ("Pathology", "p1"),
    "pathology - ii": ("Pathology", "p2"),
    "pathology - i (general pathology and haematology)": ("Pathology", "p1"),
    "pathology - ii (systemic pathology)": ("Pathology", "p2"),
    "general pathology and haematology": ("Pathology", "p1"),
    "systemic pathology": ("Pathology", "p2"),

    # Microbiology
    "general microbiology, immunology, systematic bacteriology": ("Microbiology", "p1"),
    "virology, mycology, parasitology, applied microbiology": ("Microbiology", "p2"),
    "microbiology - i": ("Microbiology", "p1"),
    "microbiology - ii": ("Microbiology", "p2"),
    "microbiology- ii": ("Microbiology", "p2"),

    # Forensic Medicine
    "forensic medicine": ("Forensic Medicine", "p1"),
    "forensic medicine(including medical jurisprudence & toxicology)": ("Forensic Medicine", "p1"),
    "forensic medicineand toxicology": ("Forensic Medicine", "p1"),

    # Community Medicine
    "community medicine": ("Community Medicine", "p1_p2"),
    "community medicine - i": ("Community Medicine", "p1"),
    "community medicine- i": ("Community Medicine", "p1"),
    "community medicine - ii": ("Community Medicine", "p2"),
    "community medicine- ii": ("Community Medicine", "p2"),
    "community medicine including humanities - i": ("Community Medicine", "p1"),
    "community medicine including humanities - ii": ("Community Medicine", "p2"),

    # Opthalmology
    "ophthalmology": ("Opthalmology", "p1"),
    "ophthalmology & oto-rhino-laryngology": ("Opthalmology_Oto-Rhino-Laryngology", "p1_p2"), 

    # Oto-Rhino-Laryngology
    "oto-rhino-laryngology": ("Oto-Rhino-Laryngology", "p1"),

    # General Medicine
    "general medicine": ("General Medicine", "p1_p2"),
    "general medicine - paper i(526081)": ("General Medicine", "p1"),
    "general medicine- paper ii(526082)": ("General Medicine", "p2"),
    "general medicine (including psychological medicine)(525082)": ("General Medicine", "p2"),
    "general medicine(including psychological medicine)": ("General Medicine", "p2"),
    "general medicine(525081)": ("General Medicine", "p1"),
    "medicine(including paediatric medicine)": ("General Medicine", "p1_p2"),

    # General Surgery
    "general surgery - paper i(526083)": ("General Surgery", "p1"),
    "general surgery- paper ii(526084)": ("General Surgery", "p2"),
    "surgery (including anaesthesia)": ("General Surgery", "p2"),
    "surgery(including anaesthesia)": ("General Surgery", "p2"),
    "surgery (including anaesthesiology, dental diseases and radiology)(525084)": ("General Surgery", "p2"),
    "surgery (including orthopaedics)(525083)": ("General Surgery", "p1"),
    "surgery(including orthopaedics)": ("General Surgery", "p1"),

    # Obstetrics & Gynaecology
    "obstetrics & gynaecology - paper i(526085)": ("Obstetrics & Gynaecology", "p1"),
    "obstetrics & gynaecology- paper ii(526086)": ("Obstetrics & Gynaecology", "p2"),
    "obstetrics and gynaecology": ("Obstetrics & Gynaecology", "p1_p2"),
    "obstetrics (including social obstetrics)(525085)": ("Obstetrics & Gynaecology", "p1"),
    "obstetrics(including social obstetrics)": ("Obstetrics & Gynaecology", "p1"),
    "gynaecology and family welfare": ("Obstetrics & Gynaecology", "p2"),
    "gynaecology, family welfare and demography(525086)": ("Obstetrics & Gynaecology", "p2"),

    # Pediatrics
    "paediatrics (including neonatology)(525087)": ("Pediatrics", "p1"),
    "paediatrics (including neonatology)": ("Pediatrics", "p1"),
    "paediatrics(including neonatology)": ("Pediatrics", "p1"),
    "paediatrics (including neonatology)(526087)": ("Pediatrics", "p1"),
}

def clean_subject_name(s):
    # Remove zero width spaces and other strange characters
    return s.lower().replace('\xa0', ' ').strip()

def map_subject(folder_name):
    cleaned = clean_subject_name(folder_name)
    if cleaned in SUBJECT_MAPPING:
        return SUBJECT_MAPPING[cleaned]
    
    # Fallback heuristic
    standard = "Unknown_Subject"
    if "anatomy" in cleaned: standard = "Anatomy"
    elif "physio" in cleaned: standard = "Physiology"
    elif "bio" in cleaned: standard = "Biochemistry"
    elif "pharma" in cleaned: standard = "Pharmacology"
    elif "patho" in cleaned: standard = "Pathology"
    elif "micro" in cleaned: standard = "Microbiology"
    elif "forensic" in cleaned: standard = "Forensic Medicine"
    elif "community" in cleaned: standard = "Community Medicine"
    elif "ophthalmo" in cleaned: standard = "Opthalmology"
    elif "oto" in cleaned or "ent" in cleaned: standard = "Oto-Rhino-Laryngology"
    elif "surgery" in cleaned: standard = "General Surgery"
    elif "med" in cleaned: standard = "General Medicine"
    elif "obs" in cleaned or "gynae" in cleaned: standard = "Obstetrics & Gynaecology"
    elif "paed" in cleaned or "ped" in cleaned: standard = "Pediatrics"

    p_str = "p1_p2"
    if " i" in cleaned or "paper 1" in cleaned or "-1" in cleaned or "paper i" in cleaned:
        p_str = "p1"
    if " ii" in cleaned or "paper 2" in cleaned or "-2" in cleaned or "paper ii" in cleaned:
        p_str = "p2"
        # Since ' ii' matches ' i' in some substring checks, make sure we overwrite p1 if it had ' i' earlier but actually is ' ii'.
    return (standard, p_str)

print("Starting to copy and organize PYQs...")
count = 0
for course_dir in source_dir.iterdir():
    if not course_dir.is_dir() or course_dir.name == "processed":
        continue
    
    for subject_dir in course_dir.iterdir():
        if not subject_dir.is_dir():
            continue
            
        std_subject, std_paper = map_subject(subject_dir.name)
        
        for year_dir in subject_dir.iterdir():
            if not year_dir.is_dir():
                continue
                
            academic_year = year_dir.name
            
            dest_dir = target_dir / std_subject / academic_year / std_paper / "pdfs"
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            for pdf_file in year_dir.glob("*.pdf"):
                dest_file = dest_dir / pdf_file.name
                if not dest_file.exists():
                    shutil.copy2(pdf_file, dest_file)
                    count += 1

print(f"Done! Copied and organized {count} files.")
