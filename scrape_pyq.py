import os
import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
from tqdm import tqdm

base_url = "https://www.tnmgrmu.ac.in"
output_dir = "data/pyq/TNMGRU/raw"

ug_courses = [
    ("FIRST M.B.B.S.", "https://www.tnmgrmu.ac.in/index.php/library/e-questions/first-m-b-b-s.html"),
    ("SECOND M.B.B.S.", "https://www.tnmgrmu.ac.in/index.php/library/e-questions/second-m-b-b-s.html"),
    ("THIRD M.B.B.S. Part I", "https://www.tnmgrmu.ac.in/index.php/library/e-questions/third-m-b-b-s-part-i.html"),
    ("THIRD M.B.B.S. Part II", "https://www.tnmgrmu.ac.in/index.php/library/e-questions/third-m-b-b-s-part-ii.html")
]

def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]+', '_', name).strip()

def download_file(url, filepath):
    # Check if exists and has some size instead of just exist to be slightly safer
    if os.path.exists(filepath):
        if os.path.getsize(filepath) > 0:
            return True # skipped
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, stream=True, headers=headers, verify=False, timeout=30)
        r.raise_for_status()
        with open(filepath, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return False # downloaded
    except Exception as e:
        return f"Error downloading {url}: {e}"

requests.packages.urllib3.disable_warnings()

downloads = []

print("Phase 1: Collecting all pyq links...")
for course_name, course_url in ug_courses:
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(course_url, headers=headers, verify=False)
        r.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch {course_url}: {e}")
        continue
        
    soup = BeautifulSoup(r.text, 'html.parser')
    tables = soup.find_all('table')
    
    for table in tables:
        current_subject = "Unknown Subject"
        subject_col_idx = 1
        
        headers_row = table.find('tr')
        if headers_row:
            headers_cells = headers_row.find_all(['th', 'td'])
            for i, cell in enumerate(headers_cells):
                if "subject" in cell.get_text(strip=True).lower():
                    subject_col_idx = i
                    break

        for row in table.find_all('tr'):
            cells = row.find_all(['th', 'td'])
            if not cells:
                continue
                
            links = row.find_all('a', href=True)
            subject_candidate = ""
            if len(cells) > subject_col_idx:
                subject_candidate = cells[subject_col_idx].get_text(strip=True)
                lowered = subject_candidate.lower()
                if subject_candidate and lowered not in ['subject', 'year', 'theory', 'mcq'] and not lowered.startswith('paper'):
                    if subject_candidate:
                        current_subject = subject_candidate
            
            for link in links:
                href = link['href']
                if href.lower().endswith('.pdf'):
                    academic_year = link.get_text(strip=True)
                    if not academic_year or academic_year.lower() in ['download', 'pdf', 'click here']:
                        academic_year = "Unknown_Year"
                    
                    full_url = urllib.parse.urljoin(base_url, href)
                    filename = os.path.basename(urllib.parse.urlparse(full_url).path)
                    
                    safe_course = sanitize_filename(course_name)
                    safe_subject = sanitize_filename(current_subject)
                    safe_year = sanitize_filename(academic_year)
                    
                    target_dir = os.path.join(output_dir, safe_course, safe_subject, safe_year)
                    os.makedirs(target_dir, exist_ok=True)
                    
                    filepath = os.path.join(target_dir, filename)
                    downloads.append({'url': full_url, 'filepath': filepath, 'filename': filename})

print(f"Phase 2: Downloading {len(downloads)} files...")

# Create the progress bar
skipped = 0
downloaded = 0
errors = 0

with tqdm(total=len(downloads), desc="Downloading PYQs", unit="file") as pbar:
    for item in downloads:
        pbar.set_postfix_str(item['filename'])
        result = download_file(item['url'], item['filepath'])
        if result is True:
            skipped += 1
        elif result is False:
            downloaded += 1
        else:
            errors += 1
            tqdm.write(result)
        pbar.update(1)

print(f"Done! Downloaded: {downloaded}, Skipped: {skipped}, Errors: {errors}")
