from flask import Flask, render_template, request, jsonify, session
import os
import google.generativeai as genai
import re
app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
PROMPT_TEMPLATE_PATH = 'prompt_template.txt'
PROMPT_ANSWER_PATH = 'prompt_answer.txt'
PROMPT_QUESTION_PATH = 'prompt_question.txt'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.secret_key = os.urandom(24)

# Gemini API Key
API_KEY = 'AIzaSyCLflM42GN6qEhkWdzBNyu8lN3NLgcK_hQ'
genai.configure(api_key=API_KEY)

def parse_model_output(text):
    sections = {
        'title': '',
        'case_type': '',
        'summary': '',
        'claims': '',
        'laws': '',
        'result': '',
        'reason': ''
    }
    patterns = {
        'title': r'## 標題：\s*(.+)',
        'case_type': r'## 案件種類：\s*(.+)',
        'summary': r'## 案件概要：\s*([\s\S]*?)## 原告請求賠償：',
        'claims': r'## 原告請求賠償：\s*([\s\S]*?)## 適用法律：',
        'laws': r'## 適用法律：\s*([\s\S]*?)## 判決結果：',
        'result': r'## 判決結果：\s*([\s\S]*?)## 判決理由：',
        'reason': r'## 判決理由：\s*([\s\S]*)'
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            sections[key] = match.group(1).strip()
    return sections

#生成推薦問題
def generate_suggested_questions(context):
    try:
        if not os.path.exists(PROMPT_QUESTION_PATH):
            print("⚠ 找不到 prompt_question.txt 檔案。")
            return []

        with open(PROMPT_QUESTION_PATH, 'r', encoding='utf-8') as f:
            prompt_template = f.read()

        truncated_context = context[:4000]  # 限制文字長度避免 API 超載
        prompt = f"{prompt_template.strip()}\n\n{truncated_context}"

        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)

        if not response or not response.text:
            return []

        return [line.strip("•-●* ") for line in response.text.strip().splitlines() if line.strip()]

    except Exception as e:
        print(f"⚠ 產生建議問題失敗：{e}")
        return []

# 分析判決書
def analyze_judgment(file_path): 
    if not os.path.exists(PROMPT_TEMPLATE_PATH):
        return "⚠ 提示詞檔案未找到，請確認 prompt_template.txt 是否存在。"
    
    try:
        with open(PROMPT_TEMPLATE_PATH, 'r', encoding='utf-8') as prompt_file:
            prompt_template = prompt_file.read()

        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()

        if not content.strip():
            return "⚠ 判決書內容為空，請上傳正確的文本。"

        prompt = f"{prompt_template}\n判決書內容如下：\n{content}"

        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        return response.text if response and response.text else "⚠ AI 沒有回傳任何分析內容。"

    except Exception as e:
        return f"⚠ 發生錯誤：{str(e)}"

# 將 AI 回傳的文字分析，提取標題、概要、法律依據等欄位
def extract_sections(result_text):
    if not isinstance(result_text, str):
        return {
            "title": "分析錯誤",
            "case_type": result_text,
            "summary": "",
            "claims": "",
            "laws": "",
            "result": "",
            "reason": ""
        }

    label_map = {
        "## 標題：": "title",
        "## 案件種類：": "case_type",
        "## 案件概要：": "summary",
        "## 原告請求賠償：": "claims",
        "## 適用法律：": "laws",
        "## 判決結果：": "result",
        "## 判決理由：": "reason"
    }

    pattern = re.compile(r"(## .+?：)\s*")
    parts = pattern.split(result_text)
    sections = {v: "" for v in label_map.values()}
    for i in range(1, len(parts), 2):
        label = parts[i].strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        key = label_map.get(label)
        if key:
            sections[key] = content
    if sections["laws"]:
        sections["laws"] = sections["laws"].replace("、", "、\n").replace("，", "，\n")
    return sections

# 上傳介面
@app.route('/')
def upload_file():
    return '''
    <!doctype html>
    <html lang="zh-Hant">
    <head>
        <meta charset="UTF-8">
        <title>判決書分析工具</title>
        <style>
            body {
                font-family: "Segoe UI", Arial, sans-serif;
                background: linear-gradient(135deg, #f1fff2, #b2f0db);
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
            }

            .upload-box {
                background-color: #fff;
                padding: 40px;
                border-radius: 12px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                text-align: center;
                max-width: 500px;
                width: 90%;
            }

            h1 {
                margin-bottom: 30px;
                color: #198754;
            }

            input[type="file"] {
                padding: 10px;
                margin-bottom: 20px;
                border: 2px dashed #ced4da;
                border-radius: 8px;
                width: 100%;
                background-color: #f8f9fa;
            }

            input[type="submit"] {
                background-color: #198754;
                color: white;
                border: none;
                padding: 12px 30px;
                border-radius: 8px;
                font-size: 16px;
                cursor: pointer;
                transition: background-color 0.3s ease;
            }

            input[type="submit"]:hover {
                background-color: #146c43;
            }
        </style>
    </head>
    <body>
        <div class="upload-box">
            <h1>判決書分析工具</h1>
            <form method="post" enctype="multipart/form-data">
                <input type="file" name="file" required>
                <br><br>
                <input type="submit" value="上傳並分析">
            </form>
        </div>
    </body>
    </html>
    '''
    
# 把 sections 組回 prompt 格式供問答使用
def format_context_for_prompt(sections):
    return (
        f"## 標題：{sections.get('title', '')}\n"
        f"## 案件種類：{sections.get('case_type', '')}\n"
        f"## 案件概要：\n{sections.get('summary', '')}\n"
        f"## 原告請求賠償：\n{sections.get('claims', '')}\n"
        f"## 適用法律：\n{sections.get('laws', '')}\n"
        f"## 判決結果：\n{sections.get('result', '')}\n"
        f"## 判決理由：\n{sections.get('reason', '')}"
    )

# 使用者上傳判決書後進入預覽頁
@app.route('/', methods=['POST'])
def upload_file_post():
    file = request.files['file']
    if file:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)

        # 讀取原始文字內容，傳給 preview
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_text = f.read()

        session['uploaded_filename'] = file.filename

        # 顯示預覽頁面
        return render_template('preview.html', filename=file.filename, content=raw_text, file_path=file_path)

# 使用者點擊「開始分析」時進行分析與解析區塊
@app.route('/ask', methods=['POST'])
def ask_question():
    user_question = request.form['question']
    chat_history = session.get('chat_history', [])
    context_data = session.get('sections', {})  # ← 初步嘗試從 session 取得

    uploaded_filename = session.get('uploaded_filename')
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_filename) if uploaded_filename else ''
    
    full_context = ''
    if uploaded_filename and os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            full_context = f.read()
    
    # 若 sections 不存在或為空，則重新分析一次
    if not context_data and full_context:
        raw_result = analyze_judgment(file_path)
        context_data = extract_sections(raw_result)
        session['sections'] = context_data

    if not full_context:
        ai_answer = "⚠ 找不到已上傳的文件資料。"
        suggested_questions = []
    else:
        try:
            history_prompt = ""
            for entry in chat_history:
                history_prompt += f"使用者：{entry['question']}\nAI：{entry['answer']}\n"

            with open(PROMPT_ANSWER_PATH, 'r', encoding='utf-8') as f:
                logic_template = f.read()

            prompt = (
                f"{logic_template.strip()}\n\n"
                f"以下是判決書全文：\n{full_context[:4000]}\n\n"
                f"{history_prompt}"
                f"使用者：{user_question}"
            )

            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt)
            ai_answer = response.text if response and hasattr(response, 'text') else "⚠ AI 無法提供回應。"

            suggested_questions = generate_suggested_questions(full_context)

        except Exception as e:
            ai_answer = f"⚠ 發生錯誤：{e}"
            suggested_questions = []

    chat_history.append({"question": user_question, "answer": ai_answer})
    session['chat_history'] = chat_history

    # 若 context_data 中欄位缺失，提供預設值避免 template 報錯
    return render_template(
        "result.html",
        user_question=user_question,
        answer=ai_answer,
        suggested_questions=suggested_questions,
        chat_history=session.get('chat_history', []),
        title=context_data.get("title", "無標題"),
        case_type=context_data.get("case_type", "無資料"),
        summary=context_data.get("summary", "無資料"),
        claims=context_data.get("claims", "無資料"),
        laws=context_data.get("laws", "無資料"),
        result=context_data.get("result", "無資料"),
        reason=context_data.get("reason", "無資料")
    )




# 使用者點擊「開始分析」時進行分析與解析區塊
@app.route('/analyze', methods=['POST'])
def analyze_uploaded_file():
    file_path = request.form.get('file_path')
    if not file_path or not os.path.exists(file_path):
        return "⚠ 找不到上傳的檔案，請重新上傳。"

    with open(file_path, 'r', encoding='utf-8') as f:
        uploaded_text = f.read()

    raw_result = analyze_judgment(file_path)
    sections = extract_sections(raw_result)

    sections["suggested_questions"] = generate_suggested_questions(uploaded_text)
    session['sections'] = {key: sections[key] for key in sections if key != "full_context"}
    session['uploaded_filename'] = os.path.basename(file_path)  # 只存檔名
    session['chat_history'] = []

    return render_template('result.html', chat_history=[], **sections)




if __name__ == '__main__':
    app.run(debug=True)
