import os
import shutil
import zipfile
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
HF_TOKEN = os.getenv('HF_TOKEN')
MODEL_ID = os.getenv('MODEL_ID')

DESKTOP = os.path.join(os.path.expanduser('~'), 'Desktop')


def print_banner():
    print("\n🤖 Byte Agents Client (Python)")
    print("Type your natural language file commands. Type 'exit' to quit.\n")


def search_files(query):
    results = []
    query = query.lower()
    known_exts = [
        'pdf', 'txt', 'doc', 'docx', 'csv', 'xlsx', 'ppt',
        'pptx', 'jpg', 'jpeg', 'png', 'zip'
    ]
    # Only search the top-level of Desktop
    try:
        files = os.listdir(DESKTOP)
    except Exception as e:
        print(f"[ERROR] Could not list Desktop: {e}")
        return results
    if query in known_exts:
        for file in files:
            clean_file = file.strip().lower()
            ext_match = clean_file.endswith(f'.{query}')
            if ext_match:
                results.append(os.path.join(DESKTOP, file))
    else:
        for file in files:
            if query in file.lower():
                results.append(os.path.join(DESKTOP, file))
    return results


def move_file(src, dst):
    shutil.move(src, dst)


def copy_file(src, dst):
    shutil.copy2(src, dst)


def edit_file(path, find_text=None, replace_text=None, append_text=None):
    if append_text:
        with open(path, 'a', encoding='utf-8') as f:
            f.write(append_text + '\n')
    elif find_text and replace_text:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        content = content.replace(find_text, replace_text)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)


def create_folder(path):
    os.makedirs(path, exist_ok=True)


def compress_files(file_list, zip_name):
    with zipfile.ZipFile(zip_name, 'w') as zipf:
        for file in file_list:
            zipf.write(file, os.path.basename(file))


def summarize_file(path):
    if not os.path.exists(path):
        print(f"[ERROR] File not found: {path}")
        return None
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    print(f"[DEBUG] Read {len(content)} characters from {path}.")
    print(f"[DEBUG] File preview: {repr(content[:100])}")
    if not content.strip():
        print(f"[ERROR] File is empty: {path}")
        return None

    # Improved chunking: overlap to avoid topic loss at boundaries
    chunk_size = 1800
    overlap = 500  # chars of overlap between chunks
    chunks = []
    i = 0
    while i < len(content):
        chunk = content[i:i+chunk_size]
        chunks.append(chunk)
        if i + chunk_size >= len(content):
            break
        i += chunk_size - overlap

    chunk_summaries = []
    for idx, chunk in enumerate(chunks):
        print(
            f"[DEBUG] Summarizing chunk {idx+1}/{len(chunks)} "
            f"(length: {len(chunk)})"
        )
        summary = call_llm(chunk)
        if summary and summary.strip():
            chunk_summaries.append(summary.strip())
        else:
            print(f"[ERROR] No summary generated for chunk {idx+1}")
    if not chunk_summaries:
        print(f"[ERROR] No summaries generated for any chunk in {path}")
        return None
    combined = '\n'.join(chunk_summaries)
    print(
        "[DEBUG] Summarizing combined chunk summaries for final summary."
    )
    final_summary = call_llm(combined)
    if not final_summary or not final_summary.strip():
        print(
            "[ERROR] No final summary generated, "
            "returning concatenated chunk summaries."
        )
        final_summary = combined
    return final_summary


def call_llm(text):
    if not HF_TOKEN:
        print("[ERROR] Hugging Face API token not set in .env")
        return None
    if not MODEL_ID:
        print("[ERROR] MODEL_ID not set in .env")
        return None
    url = f"https://api-inference.huggingface.co/models/{MODEL_ID}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": text[:2000],
        "parameters": {"max_length": 2048, "min_length": 300}
    }
    try:
        resp = requests.post(
            url, headers=headers, json=payload, timeout=60
        )
        resp.raise_for_status()
        result = resp.json()
        if isinstance(result, list):
            if 'summary_text' in result[0]:
                print(
                    f"[DEBUG] Summary: {result[0]['summary_text']}"
                )
                return result[0]['summary_text']
            elif 'generated_text' in result[0]:
                print(
                    f"[DEBUG] Generated: {result[0]['generated_text']}"
                )
                return result[0]['generated_text']
        elif isinstance(result, dict):
            if 'summary_text' in result:
                print(
                    f"[DEBUG] Summary: {result['summary_text']}"
                )
                return result['summary_text']
            elif 'generated_text' in result:
                print(
                    f"[DEBUG] Generated: {result['generated_text']}"
                )
                return result['generated_text']
    except Exception as e:
        print(f"[LLM ERROR] {e}")
    return None


def delete_file(path):
    os.remove(path)


def main():
    print_banner()
    import re

    while True:
        cmd = input('> ').strip()
        if cmd.lower() in ('exit', 'quit'):
            print('Goodbye!')
            break

        # Flexible 'find' command parsing
        if cmd.startswith('find'):
            cleaned = (
                cmd.replace('find', '')
                .replace('all', '')
                .replace('files', '')
                .replace('file', '')
                .replace('on my desktop', '')
                .strip()
            )
            if not cleaned:
                print("Please specify what to search for.")
                continue
            results = search_files(cleaned)
            if results:
                print(f"Found {len(results)} files:")
                for r in results:
                    print(r)
            else:
                print("No files found matching your search.")
            continue

        if cmd.startswith('move'):
            match = re.match(r'move\s+(.+?)\s+to\s+(.+)', cmd)
            if match:
                src = match.group(1).strip()
                dst = match.group(2).strip()
                src_path = os.path.join(DESKTOP, src)
                dst_path = os.path.join(DESKTOP, dst)
                if not os.path.exists(src_path):
                    print(f"[ERROR] Source file not found: {src}")
                else:
                    move_file(src_path, dst_path)
                    print(f"Moved {src} to {dst}")
            else:
                print("Sorry, I didn't understand that move command.")
            continue

        if cmd.startswith('copy'):
            match = re.match(r'copy\s+(.+?)\s+to\s+(.+)', cmd)
            if match:
                src = match.group(1).strip()
                dst = match.group(2).strip()
                src_path = os.path.join(DESKTOP, src)
                dst_path = os.path.join(DESKTOP, dst)
                if not os.path.exists(src_path):
                    print(f"[ERROR] Source file not found: {src}")
                else:
                    copy_file(src_path, dst_path)
                    print(f"Copied {src} to {dst}")
            else:
                print("Sorry, I didn't understand that copy command.")
            continue

        if cmd.startswith('append'):
            match = re.match(r'append\s+\"(.+?)\"\s+to\s+(.+)', cmd)
            if match:
                text = match.group(1)
                file = match.group(2).strip()
                file_path = os.path.join(DESKTOP, file)
                if not os.path.exists(file_path):
                    print(f"[ERROR] File not found: {file}")
                else:
                    edit_file(file_path, append_text=text)
                    print(f"Appended text to {file}")
            else:
                print(
                    "Sorry, I didn't understand that append command. "
                    "Use: append \"text\" to file.txt"
                )
            continue

        if cmd.startswith('replace'):
            match = re.match(
                r'replace\s+\"(.+?)\"\s+with\s+\"(.+?)\"\s+in\s+(.+)', cmd
            )
            if match:
                old = match.group(1)
                new = match.group(2)
                file = match.group(3).strip()
                file_path = os.path.join(DESKTOP, file)
                if not os.path.exists(file_path):
                    print(f"[ERROR] File not found: {file}")
                else:
                    edit_file(file_path, find_text=old, replace_text=new)
                    print(f"Replaced text in {file}")
            else:
                print(
                    "Sorry, I didn't understand that replace command. "
                    "Use: replace \"old\" with \"new\" in file.txt"
                )
            continue

        if cmd.startswith('create folder') or cmd.startswith('make folder'):
            match = re.match(r'(?:create|make) folder\s+(.+)', cmd)
            if match:
                folder = match.group(1).strip()
                folder_path = os.path.join(DESKTOP, folder)
                if os.path.exists(folder_path):
                    print(f"[ERROR] Folder already exists: {folder}")
                else:
                    create_folder(folder_path)
                    print(f"Created folder {folder}")
            else:
                print(
                    "Sorry, I didn't understand that create folder command. "
                    "Use: create folder myfolder"
                )
            continue

        if cmd.startswith('create file'):
            match = re.match(r'create file\s+(.+)', cmd)
            if match:
                file = match.group(1).strip()
                file_path = os.path.join(DESKTOP, file)
                if os.path.exists(file_path):
                    print(f"[ERROR] File already exists: {file}")
                else:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write("")
                    print(f"Created file {file}")
            else:
                print(
                    "Sorry, I didn't understand that create file command. "
                    "Use: create file myfile.txt"
                )
            continue

        if cmd.startswith('zip'):
            match = re.match(r'zip\s+(.+?)\s+as\s+(.+)', cmd)
            if match:
                files_str = match.group(1).strip()
                zip_name = match.group(2).strip()
                file_names = [f.strip() for f in files_str.split(',')]
                file_paths = [os.path.join(DESKTOP, f) for f in file_names]
                missing = [
                    f for f, p in zip(file_names, file_paths)
                    if not os.path.exists(p)
                ]
                if missing:
                    print(
                        f"[ERROR] These files were not found: "
                        f"{', '.join(missing)}"
                    )
                else:
                    zip_path = os.path.join(DESKTOP, zip_name)
                    compress_files(file_paths, zip_path)
                    print(f"Created zip archive {zip_name}")
            else:
                print(
                    "Sorry, I didn't understand that zip command. "
                    "Use: zip file1.txt, file2.txt as archive.zip"
                )
            continue

        if cmd.startswith('summarize'):
            zip_match = re.match(
                r'summarize(?: the content of)? ([^ ]+) from ([^ ]+) '
                r'and save to ([^ ]+)',
                cmd
            )
            if zip_match:
                file = zip_match.group(1).strip()
                archive = zip_match.group(2).strip()
                out_file = zip_match.group(3).strip()
                archive_path = os.path.join(DESKTOP, archive)
                if not os.path.exists(archive_path):
                    print(f"[ERROR] Archive not found: {archive}")
                    continue
                with zipfile.ZipFile(archive_path, 'r') as zipf:
                    if file not in zipf.namelist():
                        print(
                            f"[ERROR] File {file} not found in archive "
                            f"{archive}"
                        )
                        continue
                    with zipf.open(file) as f:
                        content = f.read().decode('utf-8')
                    if not content.strip():
                        print(
                            f"[ERROR] File {file} in archive "
                            f"{archive} is empty."
                        )
                        continue
                    summary = call_llm(content)
                    if not summary or not summary.strip():
                        print(
                            f"[ERROR] No summary generated for {file} "
                            f"in archive {archive}"
                        )
                        continue
                    out_path = os.path.join(DESKTOP, out_file)
                    with open(out_path, 'w', encoding='utf-8') as f:
                        f.write(summary)
                    print(f"Summary saved to {out_file}")
                continue
            elif 'and save to' in cmd:
                file = None
                out_file = None
                match = re.match(
                    r'summarize(?: the content of)? ([^ ]+?) '
                    r'and save to ([^ ]+)',
                    cmd
                )
                if match:
                    file = match.group(1).strip()
                    out_file = match.group(2).strip()
                else:
                    txts = re.findall(r'([\w\-.]+\.txt)', cmd)
                    if len(txts) >= 2:
                        file, out_file = txts[0], txts[1]
                if not file or not out_file:
                    print(
                        f"[ERROR] Could not parse input/output filenames "
                        f"from command: {cmd}"
                    )
                    continue
                file_path = os.path.join(DESKTOP, file)
                out_path = os.path.join(DESKTOP, out_file)
                summary = summarize_file(file_path)
                if summary:
                    with open(out_path, 'w', encoding='utf-8') as f:
                        f.write(summary)
                    print(f"Summary saved to {out_file}")
                else:
                    with open(out_path, 'w', encoding='utf-8') as f:
                        f.write(
                            "[ERROR] No summary generated or file is empty."
                        )
                    print(
                        f"[ERROR] No summary generated or file is empty. "
                        f"See {out_file}"
                    )
            else:
                if 'of' in cmd:
                    file = cmd.split('of')[1].strip()
                    file_path = os.path.join(DESKTOP, file)
                    summary = summarize_file(file_path)
                    if summary:
                        print(summary)
                    else:
                        print(
                            f"[ERROR] No summary generated or file is empty: "
                            f"{file}"
                        )
            continue

        if cmd.startswith('delete'):
            folder_match = re.match(
                r'delete (?:the )?(?:folder|floder)\s+(.+)', cmd
            )
            if folder_match:
                folder = (
                    folder_match.group(1)
                    .replace('from my desktop', '')
                    .strip()
                )
                path = os.path.join(DESKTOP, folder)
                if os.path.isdir(path):
                    try:
                        shutil.rmtree(path)
                        print(f"Deleted folder {folder}")
                    except Exception as e:
                        print(
                            f"[ERROR] Could not delete folder '{folder}': {e}"
                        )
                else:
                    print(
                        f"[ERROR] Folder '{folder}' not found on "
                        f"your desktop."
                    )
            else:
                file_match = re.match(r'delete (?:the )?file\s+(.+)', cmd)
                if file_match:
                    file = (
                        file_match.group(1)
                        .replace('from my desktop', '')
                        .strip()
                    )
                    path = os.path.join(DESKTOP, file)
                    if os.path.isfile(path):
                        try:
                            delete_file(path)
                            print(f"Deleted file '{file}'")
                        except Exception as e:
                            print(
                                f"[ERROR] Could not delete file "
                                f"'{file}': {e}"
                            )
                    else:
                        print(
                            f"[ERROR] File '{file}' not found on "
                            f"your desktop."
                        )
                else:
                    print(
                        "[ERROR] Please specify a valid file or folder "
                        "to delete."
                    )
            continue

        if cmd == '':
            pass
        else:
            print(
                "Sorry, I didn't understand that command."
            )


if __name__ == '__main__':
    main()
