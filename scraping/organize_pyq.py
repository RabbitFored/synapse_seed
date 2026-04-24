import os
import shutil
import sys
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:
    print("❌ tqdm not installed. Run: pip install tqdm")
    sys.exit(1)

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

    # Forensic Medicine and Toxicology
    "forensic medicine": ("Forensic Medicine and Toxicology", "p1"),
    "forensic medicine(including medical jurisprudence & toxicology)": ("Forensic Medicine and Toxicology", "p1"),
    "forensic medicineand toxicology": ("Forensic Medicine and Toxicology", "p1"),
    "forensic medicine and toxicology": ("Forensic Medicine and Toxicology", "p1"),

    # Community Medicine
    "community medicine": ("Community Medicine", "p1_p2"),
    "community medicine - i": ("Community Medicine", "p1"),
    "community medicine- i": ("Community Medicine", "p1"),
    "community medicine - ii": ("Community Medicine", "p2"),
    "community medicine- ii": ("Community Medicine", "p2"),
    "community medicine including humanities - i": ("Community Medicine", "p1"),
    "community medicine including humanities - ii": ("Community Medicine", "p2"),

    # Ophthalmology
    "ophthalmology": ("Ophthalmology", "p1"),
    # Legacy combined paper dropped — only 2 old PDFs, not worth splitting

    # ENT (Oto-Rhino-Laryngology)
    "oto-rhino-laryngology": ("ENT", "p1"),

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

    # Obstetrics and Gynaecology
    "obstetrics & gynaecology - paper i(526085)": ("Obstetrics and Gynaecology", "p1"),
    "obstetrics & gynaecology- paper ii(526086)": ("Obstetrics and Gynaecology", "p2"),
    "obstetrics and gynaecology": ("Obstetrics and Gynaecology", "p1_p2"),
    "obstetrics (including social obstetrics)(525085)": ("Obstetrics and Gynaecology", "p1"),
    "obstetrics(including social obstetrics)": ("Obstetrics and Gynaecology", "p1"),
    "gynaecology and family welfare": ("Obstetrics and Gynaecology", "p2"),
    "gynaecology, family welfare and demography(525086)": ("Obstetrics and Gynaecology", "p2"),

    # Paediatrics
    "paediatrics (including neonatology)(525087)": ("Paediatrics", "p1"),
    "paediatrics (including neonatology)": ("Paediatrics", "p1"),
    "paediatrics(including neonatology)": ("Paediatrics", "p1"),
    "paediatrics (including neonatology)(526087)": ("Paediatrics", "p1"),
}

def clean_subject_name(s):
    # Remove zero width spaces and other strange characters
    return s.lower().replace('\xa0', ' ').strip()

def map_subject(folder_name):
    cleaned = clean_subject_name(folder_name)
    if cleaned in SUBJECT_MAPPING:
        return SUBJECT_MAPPING[cleaned]
    
    # Fallback heuristic — uses canonical taxonomy names
    standard = "Unknown_Subject"
    if "anatomy" in cleaned: standard = "Anatomy"
    elif "physio" in cleaned: standard = "Physiology"
    elif "bio" in cleaned: standard = "Biochemistry"
    elif "pharma" in cleaned: standard = "Pharmacology"
    elif "patho" in cleaned: standard = "Pathology"
    elif "micro" in cleaned: standard = "Microbiology"
    elif "forensic" in cleaned: standard = "Forensic Medicine and Toxicology"
    elif "community" in cleaned: standard = "Community Medicine"
    elif "ophthalmo" in cleaned: standard = "Ophthalmology"
    elif "oto" in cleaned or "ent" in cleaned or "laryn" in cleaned: standard = "ENT"
    elif "surgery" in cleaned: standard = "General Surgery"
    elif "med" in cleaned: standard = "General Medicine"
    elif "obs" in cleaned or "gynae" in cleaned or "gynaec" in cleaned: standard = "Obstetrics and Gynaecology"
    elif "paed" in cleaned or "ped" in cleaned: standard = "Paediatrics"
    elif "ortho" in cleaned: standard = "Orthopaedics"

    p_str = "p1_p2"
    if " i" in cleaned or "paper 1" in cleaned or "-1" in cleaned or "paper i" in cleaned:
        p_str = "p1"
    if " ii" in cleaned or "paper 2" in cleaned or "-2" in cleaned or "paper ii" in cleaned:
        p_str = "p2"
    return (standard, p_str)

def main():
    print("Starting to copy and organize PYQs...")
    count = 0
    tasks = []
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
                
                for pdf_file in year_dir.glob("*.pdf"):
                    dest_file = dest_dir / pdf_file.name
                    if not dest_file.exists():
                        tasks.append((pdf_file, dest_dir, dest_file, std_subject, academic_year, std_paper))

    if tasks:
        with tqdm(total=len(tasks), desc="  Copying PDFs", unit="file", 
                  bar_format='{l_bar}{bar:30}{r_bar}', colour='magenta') as pbar:
            for pdf_file, dest_dir, dest_file, std_subject, academic_year, std_paper in tasks:
                pbar.set_postfix_str(f"{std_subject}/{academic_year}/{std_paper}")
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(pdf_file, dest_file)
                count += 1
                pbar.update(1)

    print(f"\n  ✅ Done! Processed and organized {count} files.")


if __name__ == '__main__':
    main()
