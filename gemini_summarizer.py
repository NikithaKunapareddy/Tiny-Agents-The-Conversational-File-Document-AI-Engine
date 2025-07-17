import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'models/gemini-pro')

DESKTOP = os.path.join(os.path.expanduser('~'), 'Desktop')

def summarize_with_gemini(text):
    if not GEMINI_API_KEY:
        print("[ERROR] Gemini API key not set in .env")
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": f"Summarize the following text:\n{text[:3000]}"}]}]
    }
    try:
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        summary = result['candidates'][0]['content']['parts'][0]['text']
        print(f"[DEBUG] Gemini Summary: {summary}")
        return summary
    except Exception as e:
        print(f"[Gemini ERROR] {e}")
        return None

def main():
    file = input('Enter the name of the file to summarize (on Desktop): ').strip()
    out_file = input('Enter the name of the output file (on Desktop): ').strip()
    file_path = os.path.join(DESKTOP, file)
    out_path = os.path.join(DESKTOP, out_file)
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    summary = summarize_with_gemini(content)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(summary or content)
    print(f"Summary saved to {out_file}")

if __name__ == '__main__':
    main()
