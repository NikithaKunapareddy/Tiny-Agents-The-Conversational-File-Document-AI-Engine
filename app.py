from flask import Flask, request, render_template, jsonify
import re
import os
import shutil

import agent  # Import your CLI logic

# Use a safe, writable directory for all file operations in Cloud Run
DESKTOP = '/tmp/byte_agents'
# Ensure the directory exists at startup
os.makedirs(DESKTOP, exist_ok=True)

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/command', methods=['POST'])
def handle_command():
    cmd = request.form.get('cmd', '').strip()
    if not cmd:
        return jsonify({'output': 'No command provided.'})
    output = run_command(cmd)
    return jsonify({'output': output})


def run_command(cmd):
    """Process command and return output as string."""
    try:
        # Find command
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
                return 'Please specify what to search for.'
            results = agent.search_files(cleaned)
            if results:
                return 'Found {} files:\n{}'.format(
                    len(results), '\n'.join(results)
                )
            else:
                return 'No files found matching your search.'

        # Move command
        if cmd.startswith('move'):
            match = re.match(r'move\s+(.+?)\s+to\s+(.+)', cmd)
            if match:
                src = match.group(1).strip()
                dst = match.group(2).strip()
                src_path = os.path.join(DESKTOP, src)
                dst_path = os.path.join(DESKTOP, dst)
                if not os.path.exists(src_path):
                    return f"[ERROR] Source file not found: {src}"
                agent.move_file(src_path, dst_path)
                return f"Moved {src} to {dst}"
            return "Sorry, I didn't understand that move command."

        # Copy command
        if cmd.startswith('copy'):
            match = re.match(r'copy\s+(.+?)\s+to\s+(.+)', cmd)
            if match:
                src = match.group(1).strip()
                dst = match.group(2).strip()
                src_path = os.path.join(DESKTOP, src)
                dst_path = os.path.join(DESKTOP, dst)
                if not os.path.exists(src_path):
                    return f"[ERROR] Source file not found: {src}"
                agent.copy_file(src_path, dst_path)
                return f"Copied {src} to {dst}"
            return "Sorry, I didn't understand that copy command."

        # Append command
        if cmd.startswith('append'):
            match = re.match(r'append\s+\"(.+?)\"\s+to\s+(.+)', cmd)
            if match:
                text = match.group(1)
                file = match.group(2).strip()
                file_path = os.path.join(DESKTOP, file)
                if not os.path.exists(file_path):
                    return f"[ERROR] File not found: {file}"
                agent.edit_file(file_path, append_text=text)
                return f"Appended text to {file}"
            return (
                "Sorry, I didn't understand that append command. "
                "Use: append \"text\" to file.txt"
            )

        # Replace command
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
                    return f"[ERROR] File not found: {file}"
                agent.edit_file(file_path, find_text=old, replace_text=new)
                return f"Replaced text in {file}"
            return (
                "Sorry, I didn't understand that replace command. "
                "Use: replace \"old\" with \"new\" in file.txt"
            )

        # Create folder command
        if cmd.startswith('create folder') or cmd.startswith('make folder'):
            match = re.match(r'(?:create|make) folder\s+(.+)', cmd)
            if match:
                folder = match.group(1).strip()
                folder_path = os.path.join(DESKTOP, folder)
                if os.path.exists(folder_path):
                    return f"[ERROR] Folder already exists: {folder}"
                agent.create_folder(folder_path)
                return f"Created folder {folder}"
            return (
                "Sorry, I didn't understand that create folder command. "
                "Use: create folder myfolder"
            )

        # Create file command
        if cmd.startswith('create file'):
            match = re.match(r'create file\s+(.+)', cmd)
            if match:
                file = match.group(1).strip()
                file_path = os.path.join(DESKTOP, file)
                if os.path.exists(file_path):
                    return f"[ERROR] File already exists: {file}"
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("")
                return f"Created file {file}"
            return (
                "Sorry, I didn't understand that create file command. "
                "Use: create file myfile.txt"
            )

        # Zip command
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
                    return (
                        f"[ERROR] These files were not found: "
                        f"{', '.join(missing)}"
                    )
                zip_path = os.path.join(DESKTOP, zip_name)
                agent.compress_files(file_paths, zip_path)
                return f"Created zip archive {zip_name}"
            return (
                "Sorry, I didn't understand that zip command. "
                "Use: zip file1.txt, file2.txt as archive.zip"
            )

        # Delete file/folder command
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
                        return f"Deleted folder {folder}"
                    except Exception as e:
                        return (
                            f"[ERROR] Could not delete folder "
                            f"'{folder}': {e}"
                        )
                else:
                    return (
                        f"[ERROR] Folder '{folder}' not found "
                        f"on your desktop."
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
                            agent.delete_file(path)
                            return f"Deleted file '{file}'"
                        except Exception as e:
                            return (
                                f"[ERROR] Could not delete file "
                                f"'{file}': {e}"
                            )
                    else:
                        return (
                            f"[ERROR] File '{file}' not found "
                            f"on your desktop."
                        )
                else:
                    return (
                        "[ERROR] Please specify a valid file or "
                        "folder to delete."
                    )

        # Summarize command
        if cmd.startswith('summarize'):
            if 'and save to' in cmd:
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
                    else:
                        return (
                            f"[ERROR] Could not parse input/output "
                            f"filenames from command: {cmd}"
                        )
                file_path = os.path.join(DESKTOP, file)
                out_path = os.path.join(DESKTOP, out_file)
                summary = agent.summarize_file(file_path)
                if summary:
                    with open(out_path, 'w', encoding='utf-8') as f:
                        f.write(summary)
                    return f"Summary saved to {out_file}"
                else:
                    error_msg = (
                        "[ERROR] No summary generated or file is empty."
                    )
                    with open(out_path, 'w', encoding='utf-8') as f:
                        f.write(error_msg)
                    return (
                        f"[ERROR] No summary generated or file is empty. "
                        f"See {out_file}"
                    )
            else:
                if 'of' in cmd:
                    file = cmd.split('of')[1].strip()
                    file_path = os.path.join(DESKTOP, file)
                    summary = agent.summarize_file(file_path)
                    if summary:
                        return summary
                    else:
                        return (
                            f"[ERROR] No summary generated or "
                            f"file is empty: {file}"
                        )
        return "Sorry, I didn't understand that command."
    except Exception as e:
        return f"[ERROR] Exception: {e}"


if __name__ == '__main__':
    app.run(debug=True)
