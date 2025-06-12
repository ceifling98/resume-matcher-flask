from flask import Flask, render_template, request, send_file
import os
import re
import pdfplumber
import docx2txt
from io import BytesIO
from fpdf import FPDF

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def extract_text(file):
    if file.filename.endswith('.pdf'):
        with pdfplumber.open(file) as pdf:
            return '\n'.join([page.extract_text() or "" for page in pdf.pages])
    elif file.filename.endswith('.docx'):
        return docx2txt.process(file)
    elif file.filename.endswith('.txt'):
        return file.read().decode('utf-8')
    return ""


def clean_text(text):
    return re.sub(r'[^a-zA-Z\s]', '', text.lower())


def highlight_keywords(resume, keywords):
    for word in sorted(keywords, key=len, reverse=True):
        resume = re.sub(fr'(?<!\w)({re.escape(word)})(?!\w)', r'<mark>\1</mark>', resume, flags=re.IGNORECASE)
    return resume


@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    if request.method == 'POST':
        resume_file = request.files['resume_file']
        job_file = request.files['job_file']

        resume_text = extract_text(resume_file)
        job_text = extract_text(job_file)

        resume_words = set(clean_text(resume_text).split())
        job_words = set(clean_text(job_text).split())

        matched = sorted(resume_words & job_words)
        missing = sorted(job_words - resume_words)
        match_score = round(len(matched) / len(job_words) * 100, 2) if job_words else 0

        highlighted_resume = highlight_keywords(resume_text, matched)

        # Save result for export
        request.environ['resume_result'] = {
            'match_score': match_score,
            'matched_keywords': matched,
            'missing_keywords': missing,
            'resume_raw': resume_text,
            'highlighted_resume': highlighted_resume
        }

        result = request.environ['resume_result']

    return render_template('index.html', result=result)


@app.route('/download/<filetype>')
def download(filetype):
    result = request.environ.get('resume_result')
    if not result:
        return "No results to download.", 400

    content = f"Score: {result['match_score']}%\n\nMatched Keywords:\n" + \
              ', '.join(result['matched_keywords']) + "\n\nMissing Keywords:\n" + \
              ', '.join(result['missing_keywords']) + "\n\nResume Text:\n" + result['resume_raw']

    if filetype == 'txt':
        return send_file(BytesIO(content.encode('utf-8')), download_name='results.txt', as_attachment=True)

    elif filetype == 'csv':
        csv_content = "Keyword,Type\n" + \
                      '\n'.join([f"{kw},Matched" for kw in result['matched_keywords']] +
                                 [f"{kw},Missing" for kw in result['missing_keywords']])
        return send_file(BytesIO(csv_content.encode('utf-8')), download_name='results.csv', as_attachment=True)

    elif filetype == 'pdf':
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Arial", size=12)
        for line in content.split('\n'):
            pdf.multi_cell(0, 10, line)
        pdf_bytes = BytesIO()
        pdf.output(pdf_bytes)
        pdf_bytes.seek(0)
        return send_file(pdf_bytes, download_name='results.pdf', as_attachment=True)

    return "Unsupported format.", 400


if __name__ == '__main__':
    app.run(debug=True)
