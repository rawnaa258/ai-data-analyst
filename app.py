import builtins
import io
import json
import os
import re
import time
import uuid
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
from google import genai
from google.genai import types

# البرنامج بيجرب الموديلات دي بالترتيب لو واحد منها زحمة أو مش موجود
MODELS = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3-flash-preview"]

# على السيرفر بنحط APP_MODE = "server" في الـ Secrets، فبيشتغل بوضع الاستضافة
SERVER_MODE = os.environ.get("APP_MODE", "").lower() == "server"

# ---------- النصوص (عربي / إنجليزي) ----------
STR = {
    "ar": {
        "title": "محلل البيانات بالذكاء الاصطناعي",
        "api_label": "مفتاح Gemini (API Key)",
        "api_caption": "المفتاح بيفضل على جهازك ومش بيتحفظ في أي مكان.",
        "upload": "ارفعي ملف Excel أو CSV",
        "no_tables": "مالقيتش أي جدول في الملف ده.",
        "uploaded_ok": "تم رفع الملف! لقيت {n} جدول.",
        "choose_table": "اختاري الجدول اللي عايزة تشتغلي عليه",
        "tab_preview": "معاينة البيانات",
        "tab_analysis": "التحليل",
        "tab_charts": "الرسوم البيانية",
        "tab_summary": "الملخص الذكي",
        "tab_chat": "الدردشة",
        "rows": "عدد الصفوف",
        "cols": "عدد الأعمدة",
        "missing": "القيم الناقصة",
        "missing_per_col": "القيم الناقصة في كل عمود",
        "missing_count": "عدد الناقص",
        "num_stats": "إحصائيات الأعمدة الرقمية",
        "no_numeric": "مفيش أعمدة رقمية في الملف ده.",
        "need_numeric": "محتاجين عمود رقمي واحد على الأقل عشان نرسم.",
        "chart_type": "نوع الرسم",
        "chart_bar": "أعمدة",
        "chart_line": "خطي",
        "chart_pie": "دائري",
        "x_col": "العمود الأفقي (X)",
        "y_col": "العمود الرقمي (Y)",
        "summary_title": "ملخص: {name}",
        "fold_open": "فتح الملخص",
        "fold_close": "طي الملخص",
        "del_summary": "حذف الملخص ده",
        "need_key": "حطي الـ API Key في الشريط الجانبي (على الشمال) الأول.",
        "need_key_short": "حطي الـ API Key في الشريط الجانبي الأول.",
        "btn_rewrite": "إعادة كتابة الملخص",
        "btn_write": "اكتبلي الملخص",
        "spin_summary": "Gemini بيحلل البيانات...",
        "doc_sub": "من ملف: {file}",
        "save_word": "📄 حفظ كـ Word",
        "save_pdf": "📕 حفظ كـ PDF",
        "install_libs": "عشان تحفظي Word/PDF ثبّتي المكتبات بالأمر ده في الشاشة السودا:",
        "details": "تفاصيل",
        "saved_ok": "اتحفظ الملف في فولدر Downloads باسم: {name}",
        "others_exp": "ملخصات محفوظة لجداول تانية ({n})",
        "other_from": "**{table}** (من ملف {file})",
        "chat_title": "اسألي ملفك أي سؤال",
        "chat_hint": "مثال: إيه أعلى شهر في المبيعات؟ أو: متوسط المبيعات لكل منتج؟",
        "clear_chat": "مسح المحادثة",
        "chat_input": "اكتبي سؤالك أو سجّلي رسالة صوتية...",
        "spin_listen": "بسمع الرسالة الصوتية...",
        "spin_think": "بفكر وبحسب...",
        "calc_fail": "معرفتش أحسب الإجابة دي. جربي تصيغي السؤال بشكل تاني.",
        "result_label": "النتيجة:",
        "copy": "نسخ",
        "delete_msg": "حذف الرسالة",
        "none": "لا يوجد",
        "quota_err": (
            "خلّصتي الحصة المجانية اليومية من Gemini لكل الموديلات. "
            "جربي تاني بعد ما الحصة تتجدد (غالبًا خلال كام ساعة)، "
            "أو استخدمي مفتاح من مشروع جديد."
        ),
        "generic_err": "حصلت مشكلة: {msg}",
        "facts": (
            "\nعدد الصفوف: {n}\nأسماء الأعمدة وأنواعها:\n{dtypes}\n\n"
            "القيم الناقصة:\n{missing}\n\nإحصائيات الأعمدة الرقمية:\n{stats}\n\n"
            "أول 15 صف من البيانات:\n{head}\n"
        ),
        "summary_prompt": (
            "إنت محلل بيانات خبير. دي معلومات عن ملف بيانات رفعه المستخدم:\n\n{facts}\n\n"
            "اكتب بالعربي تقرير قصير وواضح فيه:\n"
            "1. نظرة عامة: الملف ده عن إيه\n"
            "2. أهم النتائج والاتجاهات (اذكر أرقام حقيقية من البيانات بس)\n"
            "3. أي مشاكل في جودة البيانات\n"
            "4. توصيات عملية\n\n"
            "متخترعش أي رقم مش موجود في المعلومات اللي فوق."
        ),
        "code_prompt": (
            "عندك جدول بيانات في pandas اسمه df.\nالأعمدة وأنواعها:\n{dtypes}\n\n"
            "أول 5 صفوف:\n{head}\n\nسؤال المستخدم: {question}\n\n"
            "اكتب كود Python فقط (من غير شرح ومن غير import) بيحسب الإجابة\n"
            "وبيحط الناتج في متغير اسمه result.\n"
            "استخدم df و pd بس، ومتعدّلش df الأصلي. اكتب الكود بس."
        ),
        "fix_code": "\n\nالكود اللي كتبته طلع فيه خطأ: {error}\nصلّحه واكتب الكود بس.",
        "answer_prompt": (
            "سؤال المستخدم: {question}\n\nنتيجة الحساب من البيانات:\n{result}\n\n"
            "اكتب إجابة قصيرة وواضحة بالعربي بناءً على النتيجة دي بس.\n"
            "متخترعش أي رقم مش موجود فيها."
        ),
    },
    "en": {
        "title": "AI Data Analyst",
        "api_label": "Gemini API Key",
        "api_caption": "The key stays on your computer and is not saved anywhere.",
        "upload": "Upload an Excel or CSV file",
        "no_tables": "No tables were found in this file.",
        "uploaded_ok": "File uploaded! Found {n} table(s).",
        "choose_table": "Choose the table to work on",
        "tab_preview": "Data Preview",
        "tab_analysis": "Analysis",
        "tab_charts": "Charts",
        "tab_summary": "AI Summary",
        "tab_chat": "Chat",
        "rows": "Rows",
        "cols": "Columns",
        "missing": "Missing values",
        "missing_per_col": "Missing values per column",
        "missing_count": "Missing count",
        "num_stats": "Numeric column statistics",
        "no_numeric": "There are no numeric columns in this file.",
        "need_numeric": "At least one numeric column is needed to draw a chart.",
        "chart_type": "Chart type",
        "chart_bar": "Bar",
        "chart_line": "Line",
        "chart_pie": "Pie",
        "x_col": "Horizontal column (X)",
        "y_col": "Numeric column (Y)",
        "summary_title": "Summary: {name}",
        "fold_open": "Expand summary",
        "fold_close": "Collapse summary",
        "del_summary": "Delete this summary",
        "need_key": "Enter your API Key in the sidebar (on the left) first.",
        "need_key_short": "Enter your API Key in the sidebar first.",
        "btn_rewrite": "Rewrite summary",
        "btn_write": "Write the summary",
        "spin_summary": "Gemini is analyzing the data...",
        "doc_sub": "From file: {file}",
        "save_word": "📄 Save as Word",
        "save_pdf": "📕 Save as PDF",
        "install_libs": "To save Word/PDF, install the libraries with this command in the terminal:",
        "details": "Details",
        "saved_ok": "File saved in your Downloads folder as: {name}",
        "others_exp": "Saved summaries for other tables ({n})",
        "other_from": "**{table}** (from file {file})",
        "chat_title": "Ask your file anything",
        "chat_hint": "Example: Which month has the highest sales? Or: average sales per product?",
        "clear_chat": "Clear chat",
        "chat_input": "Type your question or record a voice message...",
        "spin_listen": "Listening to the voice message...",
        "spin_think": "Thinking and calculating...",
        "calc_fail": "I couldn't calculate that answer. Try rephrasing the question.",
        "result_label": "Result:",
        "copy": "Copy",
        "delete_msg": "Delete message",
        "none": "None",
        "quota_err": (
            "You've used up the free daily quota of Gemini for all models. "
            "Try again after the quota resets (usually within a few hours), "
            "or use a key from a new project."
        ),
        "generic_err": "Something went wrong: {msg}",
        "facts": (
            "\nNumber of rows: {n}\nColumn names and types:\n{dtypes}\n\n"
            "Missing values:\n{missing}\n\nStatistics of numeric columns:\n{stats}\n\n"
            "First 15 rows of the data:\n{head}\n"
        ),
        "summary_prompt": (
            "You are an expert data analyst. Here is information about a data file "
            "the user uploaded:\n\n{facts}\n\n"
            "Write a short, clear report in English with:\n"
            "1. Overview: what the file is about\n"
            "2. Key findings and trends (cite only real numbers from the data)\n"
            "3. Any data quality issues\n"
            "4. Practical recommendations\n\n"
            "Do not invent any number that is not in the information above."
        ),
        "code_prompt": (
            "You have a pandas DataFrame named df.\nColumns and types:\n{dtypes}\n\n"
            "First 5 rows:\n{head}\n\nUser question: {question}\n\n"
            "Write Python code only (no explanation, no imports) that computes the answer\n"
            "and puts the result in a variable named result.\n"
            "Use only df and pd, and do not modify the original df. Output the code only."
        ),
        "fix_code": "\n\nThe code you wrote raised an error: {error}\nFix it and output the code only.",
        "answer_prompt": (
            "User question: {question}\n\nCalculation result from the data:\n{result}\n\n"
            "Write a short, clear answer in English based only on this result.\n"
            "Do not invent any number that is not in it."
        ),
    },
}


def t(key, **kw):
    """بيرجّع النص باللغة الحالية (عربي أو إنجليزي)."""
    lang = st.session_state.get("lang", "ar")
    text = STR[lang].get(key) or STR["ar"].get(key, key)
    return text.format(**kw) if kw else text


def disp(name):
    """اسم الجدول للعرض (جدول -> Table في الإنجليزي)."""
    if st.session_state.get("lang") == "en":
        return str(name).replace(" - جدول ", " - Table ")
    return str(name)


def ui_rtl():
    return st.session_state.get("lang", "ar") == "ar"


def is_rtl_text(text):
    return bool(re.search(r"[\u0600-\u06FF]", text))


st.set_page_config(page_title="AI Data Analyst", layout="wide")
st.session_state.setdefault("lang", "ar")

RTL_CSS = """
<style>
[data-testid="stMain"], [data-testid="stMainBlockContainer"],
[data-testid="stSidebarContent"] { direction: rtl; text-align: right; }
[data-testid="stDataFrame"], [data-testid="stPlotlyChart"],
[data-testid="stSidebar"] input[type="password"] { direction: ltr; }
[data-testid="stChatInput"] textarea { direction: rtl; text-align: right; }
</style>
"""
if st.session_state.lang == "ar":
    st.markdown(RTL_CSS, unsafe_allow_html=True)


def toggle_lang():
    st.session_state.lang = "en" if st.session_state.lang == "ar" else "ar"


if ui_rtl():  # في الوضع العربي أول عمود بيبقى على اليمين
    lang_col, title_col = st.columns([1, 12], vertical_alignment="center")
else:
    title_col, lang_col = st.columns([12, 1], vertical_alignment="center")
title_col.title(t("title"))
lang_col.button(
    "EN" if st.session_state.lang == "ar" else "AR",
    key="lang_btn",
    on_click=toggle_lang,
    help="Switch language / تغيير اللغة",
)

# ---------- الشريط الجانبي: مفتاح Gemini ----------
api_key = st.sidebar.text_input(
    t("api_label"), type="password", value=st.session_state.get("api_key_saved", "")
)
st.session_state["api_key_saved"] = api_key
st.sidebar.caption(t("api_caption"))


# ---------- دوال مساعدة للدردشة ----------
def ask_gemini(client, prompt):
    """بيجرب الموديلات بالترتيب، وبيعيد المحاولة لو الموديل زحمة (503)."""
    last_error = None
    for model in MODELS:
        for attempt in range(3):
            try:
                response = client.models.generate_content(model=model, contents=prompt)
                return response.text
            except Exception as e:
                last_error = e
                msg = str(e)
                if "503" in msg or "UNAVAILABLE" in msg:
                    time.sleep(3 * (attempt + 1))  # استنى وجرب تاني
                    continue
                if (
                    "404" in msg or "NOT_FOUND" in msg
                    or "429" in msg or "RESOURCE_EXHAUSTED" in msg
                ):
                    break  # الموديل مش متاح أو حصته خلصت، جرب اللي بعده
                raise
    raise last_error


def friendly_error(e):
    msg = str(e)
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
        return t("quota_err")
    return t("generic_err", msg=msg)


def transcribe(client, audio_file):
    """بيحوّل الرسالة الصوتية لنص باستخدام Gemini."""
    audio_bytes = audio_file.getvalue() if hasattr(audio_file, "getvalue") else audio_file.read()
    part = types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")
    text = ask_gemini(
        client,
        [
            "Transcribe the speech in this audio exactly as spoken (usually Arabic or English). "
            "Output only the text, with no explanation.",
            part,
        ],
    )
    return text.strip()


def clean_code(text):
    """بيشيل علامات ``` لو Gemini حطها حوالين الكود."""
    text = text.strip()
    text = re.sub(r"^```(?:python)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


FORBIDDEN = [
    r"\bimport\b", r"\bopen\s*\(", r"\bexec\b", r"\beval\b", r"__",
    r"\bos\b", r"\bsys\b", r"\bsubprocess\b", r"\binput\s*\(",
    r"\bcompile\b", r"\bglobals\b", r"\blocals\b", r"\bgetattr\b",
    r"\bsetattr\b", r"\bdelattr\b", r"\bread_\w+", r"\bto_\w+\s*\(",
]
ALLOWED_BUILTINS = [
    "len", "sum", "min", "max", "abs", "round", "sorted", "range", "list",
    "dict", "set", "tuple", "str", "int", "float", "bool", "enumerate",
    "zip", "map", "filter", "any", "all",
]


def run_code(code, df):
    """بينفذ الكود في بيئة مقيّدة (من غير import ولا ملفات)."""
    for pattern in FORBIDDEN:
        if re.search(pattern, code):
            raise ValueError("الكود فيه أمر مش مسموح بيه لأسباب أمان.")
    safe_builtins = {n: getattr(builtins, n) for n in ALLOWED_BUILTINS}
    env = {"df": df.copy(), "pd": pd, "__builtins__": safe_builtins}
    exec(code, env)
    if "result" not in env:
        raise ValueError("الكود ما حطش الناتج في متغير result.")
    return env["result"]


def result_to_text(result):
    if isinstance(result, (pd.DataFrame, pd.Series)):
        text = result.to_string()
    else:
        text = str(result)
    return text[:3000]


# ---------- دوال تقسيم الشيت لجداول ----------
def _split_axis(frame, axis):
    """بيقسم على الصفوف الفاضية (axis=0) أو الأعمدة الفاضية (axis=1)."""
    empty = frame.isna().all(axis=1) if axis == 0 else frame.isna().all(axis=0)
    parts, start = [], None
    for i, is_empty in enumerate(empty.tolist()):
        if not is_empty and start is None:
            start = i
        elif is_empty and start is not None:
            parts.append((start, i))
            start = None
    if start is not None:
        parts.append((start, len(empty)))
    if axis == 0:
        return [frame.iloc[a:b, :] for a, b in parts]
    return [frame.iloc[:, a:b] for a, b in parts]


def split_blocks(frame):
    """بيلاقي كل الجداول اللي في الشيت (بينهم صف أو عمود فاضي)."""
    # نشيل الصفوف والأعمدة الفاضية من الأطراف بس (مش اللي في النص)
    rows = frame.notna().any(axis=1).to_numpy().nonzero()[0]
    cols = frame.notna().any(axis=0).to_numpy().nonzero()[0]
    if len(rows) == 0 or len(cols) == 0:
        return []
    frame = frame.iloc[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
    for axis in (0, 1):
        parts = _split_axis(frame, axis)
        if len(parts) > 1:
            result = []
            for part in parts:
                result += split_blocks(part)
            return result
    return [frame]


def block_to_df(block):
    """بيحوّل الجزء ده لجدول: أول صف عناوين، والباقي بيانات."""
    block = block.reset_index(drop=True)
    header = [
        str(h) if pd.notna(h) else f"عمود {i + 1}"
        for i, h in enumerate(block.iloc[0].tolist())
    ]
    seen, names = {}, []
    for h in header:  # لو في عناوين مكررة
        if h in seen:
            seen[h] += 1
            names.append(f"{h}_{seen[h]}")
        else:
            seen[h] = 0
            names.append(h)
    out = block.iloc[1:].reset_index(drop=True)
    out.columns = names
    return out.infer_objects()


def load_tables(uploaded):
    """بيرجّع قاموس: اسم الجدول -> الجدول (من كل الشيتات)."""
    if uploaded.name.endswith(".csv"):
        sheets = {"CSV": pd.read_csv(uploaded, header=None, skip_blank_lines=False)}
    else:
        sheets = pd.read_excel(uploaded, sheet_name=None, header=None)

    tables = {}
    for sheet_name, raw in sheets.items():
        blocks = [b for b in split_blocks(raw) if len(b) >= 2]
        for i, block in enumerate(blocks, start=1):
            label = f"{sheet_name} - جدول {i}" if len(blocks) > 1 else str(sheet_name)
            tables[label] = block_to_df(block)
    return tables


# ---------- حفظ الملخصات على الجهاز ----------
SUMMARIES_FILE = Path(__file__).parent / "summaries.json"


def load_summaries():
    if SERVER_MODE:
        return {}
    try:
        return json.loads(SUMMARIES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_summaries(data):
    if SERVER_MODE:
        return
    SUMMARIES_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def delete_summary(key):
    st.session_state.summaries.pop(key, None)
    st.session_state.setdefault("collapsed_summaries", set()).discard(key)
    st.session_state.setdefault("open_saved", set()).discard(key)
    save_summaries(st.session_state.summaries)


def toggle_saved(key):
    """فتح/قفل ملخص محفوظ في قايمة الملخصات التانية."""
    st.session_state.setdefault("open_saved", set()).symmetric_difference_update({key})


def wide_button(label, **kwargs):
    try:
        return st.button(label, width="stretch", **kwargs)
    except TypeError:  # نسخة Streamlit قديمة
        return st.button(label, use_container_width=True, **kwargs)


def safe_download_button(container, label, **kwargs):
    """زرار تحميل مبيعملش إعادة تشغيل للصفحة."""
    try:
        return container.download_button(label, on_click="ignore", **kwargs)
    except TypeError:
        return container.download_button(label, **kwargs)


def toggle_summary(key):
    """طي/فتح الملخص."""
    st.session_state.setdefault("collapsed_summaries", set()).symmetric_difference_update({key})


def save_to_downloads(data, table_name, ext):
    """بيحفظ الملف في فولدر Downloads باسم الجدول."""
    folder = Path.home() / "Downloads"
    folder.mkdir(exist_ok=True)
    safe = re.sub(r'[\\/:*?"<>|]', "_", str(table_name)).strip(" .") or "ملخص"
    path = folder / f"{safe}.{ext}"
    n = 2
    while path.exists():  # لو الاسم موجود، نضيف رقم بدل ما نمسح القديم
        path = folder / f"{safe} ({n}).{ext}"
        n += 1
    path.write_bytes(data)
    return path


# ---------- تصدير الملخص (Word / PDF) ----------
def parse_markdown(text):
    """بيحوّل نص الملخص لقائمة (نوع، نص): عناوين ونقط وفقرات."""
    blocks = []
    for raw in text.splitlines():
        line = raw.strip().replace("`", "")
        if not line:
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            blocks.append((f"h{min(len(m.group(1)), 3)}", m.group(2)))
            continue
        m = re.match(r"^[-*•]\s+(.*)", line)
        if m:
            blocks.append(("bullet", "• " + m.group(1)))
            continue
        blocks.append(("p", line))
    return blocks


def summary_to_docx(title, subtitle, text, rtl=True):
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    doc = Document()

    def add_par(content, size=12, bold_all=False):
        p = doc.add_paragraph()
        pPr = p._p.get_or_add_pPr()
        if rtl:
            pPr.append(OxmlElement("w:bidi"))  # اتجاه الفقرة من اليمين لليسار
        sp = OxmlElement("w:spacing")
        sp.set(qn("w:after"), "120")
        pPr.append(sp)
        for part in re.split(r"(\*\*.+?\*\*)", content):
            if not part:
                continue
            bold = bold_all or (part.startswith("**") and part.endswith("**"))
            run = p.add_run(part.strip("*") if part.startswith("**") else part)
            rPr = run._r.get_or_add_rPr()
            rf = OxmlElement("w:rFonts")
            for a in ("w:ascii", "w:hAnsi", "w:cs"):
                rf.set(qn(a), "Arial")
            rPr.append(rf)
            if bold:
                rPr.append(OxmlElement("w:b"))
                rPr.append(OxmlElement("w:bCs"))
            for tag in ("w:sz", "w:szCs"):
                el = OxmlElement(tag)
                el.set(qn("w:val"), str(int(size * 2)))
                rPr.append(el)
            if rtl:
                rPr.append(OxmlElement("w:rtl"))

    add_par(title, size=20, bold_all=True)
    add_par(subtitle, size=10)
    sizes = {"h1": 18, "h2": 16, "h3": 14}
    for kind, content in parse_markdown(text):
        if kind in sizes:
            add_par(content, size=sizes[kind], bold_all=True)
        else:
            add_par(content, size=12)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _find_arabic_font():
    candidates = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\tahoma.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        str(Path(__file__).parent / "fonts" / "DejaVuSans.ttf"),
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    raise FileNotFoundError("مالقيتش خط بيدعم العربي على الجهاز.")


def summary_to_pdf(title, subtitle, text, rtl=True):
    import arabic_reshaper
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    try:
        from bidi import get_display
    except ImportError:
        from bidi.algorithm import get_display

    font = "ArabicFont"
    if font not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font, _find_arabic_font()))

    # بعض نسخ مكتبة bidi مبتقلبش شكل الأقواس في النص العربي، فبنتأكد ونصلّحها
    swap = str.maketrans("()[]{}<>", ")(][}{><")
    needs_swap = get_display("(ب)", base_dir="R") != "(ب)"

    def vis(t):  # تشكيل الحروف العربي + ترتيب الاتجاه
        if not rtl:
            return t
        out = get_display(arabic_reshaper.reshape(t), base_dir="R")
        return out.translate(swap) if needs_swap else out

    width, height = A4
    margin = 50
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    state = {"y": height - margin}

    def draw(content, size=12, indent=0, gap=6):
        content = content.replace("**", "")
        line_h = size * 1.6
        max_w = width - 2 * margin - indent
        lines, cur = [], ""
        for w in content.split():
            trial = (cur + " " + w).strip()
            if pdfmetrics.stringWidth(vis(trial), font, size) <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        for ln in lines:
            if state["y"] - line_h < margin:
                c.showPage()
                state["y"] = height - margin
            c.setFont(font, size)
            if rtl:
                c.drawRightString(width - margin - indent, state["y"] - size, vis(ln))
            else:
                c.drawString(margin + indent, state["y"] - size, ln)
            state["y"] -= line_h
        state["y"] -= gap

    draw(title, size=20, gap=2)
    draw(subtitle, size=10, gap=14)
    sizes = {"h1": 18, "h2": 16, "h3": 14}
    for kind, content in parse_markdown(text):
        if kind in sizes:
            draw(content, size=sizes[kind], gap=8)
        elif kind == "bullet":
            draw(content, size=12, indent=12, gap=4)
        else:
            draw(content, size=12)
    c.save()
    return buf.getvalue()


# ---------- أدوات رسائل الشات (نسخ + حذف) ----------
CHAT_CSS = """
<style>
[class*="st-key-actions_"] { opacity: 0; transition: opacity .15s ease-in-out; }
[data-testid="stChatMessage"]:hover [class*="st-key-actions_"],
[class*="st-key-actions_"]:focus-within { opacity: 1; }
[class*="st-key-actions_"] button { padding: 0.1rem 0.6rem; min-height: 2rem; }
</style>
"""


def copy_button(text):
    """زرار نسخ بيشتغل في المتصفح مباشرة (من غير سكرول)."""
    safe = json.dumps(text).replace("</", "<\\/")
    html = f"""
    <style>
      html, body {{ margin: 0; padding: 0; overflow: hidden; background: transparent; }}
      button {{ background: transparent; border: 1px solid #666; border-radius: 8px;
                cursor: pointer; font-size: 15px; height: 34px; padding: 0 12px;
                display: block; margin: 2px 0 0 auto; }}
    </style>
    <button id="b" title="{t('copy')}">📋</button>
    <script>
    const t = {safe};
    const b = document.getElementById("b");
    b.onclick = async () => {{
        try {{ await navigator.clipboard.writeText(t); }}
        catch (e) {{
            const a = document.createElement("textarea");
            a.value = t; document.body.appendChild(a); a.select();
            document.execCommand("copy"); a.remove();
        }}
        b.textContent = "✅";
        setTimeout(() => {{ b.textContent = "📋"; }}, 1200);
    }};
    </script>
    """
    if hasattr(st, "iframe"):  # النسخ الجديدة من Streamlit
        st.iframe(html, height=42)
    else:  # النسخ الأقدم
        components.html(html, height=42, scrolling=False)


def delete_message(msg_id):
    st.session_state.messages = [
        m for m in st.session_state.messages if m.get("id") != msg_id
    ]


def render_message(m):
    m.setdefault("id", uuid.uuid4().hex)
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        with st.container(key=f"actions_{m['id']}"):
            if ui_rtl():
                c1, c2, _ = st.columns([1, 1, 14], vertical_alignment="center")
            else:
                _, c1, c2 = st.columns([14, 1, 1], vertical_alignment="center")
            with c1:
                copy_button(m["content"])
            with c2:
                st.button(
                    "🗑",
                    key=f"del_{m['id']}",
                    help=t("delete_msg"),
                    on_click=delete_message,
                    args=(m["id"],),
                )


file = st.file_uploader("📂 Excel / CSV", type=["csv", "xlsx"], key="uploader")

if file:
    tables = load_tables(file)
    if not tables:
        st.error(t("no_tables"))
        st.stop()

    st.success(t("uploaded_ok", n=len(tables)))

    if len(tables) > 1:
        keys = list(tables.keys())
        labels = [disp(k) for k in keys]
        saved = st.session_state.get("current_table")
        chosen = st.selectbox(
            t("choose_table"), labels, index=keys.index(saved) if saved in keys else 0
        )
        table_name = keys[labels.index(chosen)]
    else:
        table_name = list(tables.keys())[0]
    df = tables[table_name]

    # لو غيّرتي الجدول، نمسح المحادثة القديمة
    if st.session_state.get("current_table") != table_name:
        st.session_state["current_table"] = table_name
        st.session_state["messages"] = []

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [t("tab_preview"), t("tab_analysis"), t("tab_charts"), t("tab_summary"), t("tab_chat")]
    )

    numeric_cols = df.select_dtypes(include="number").columns.tolist()

    # ---------- التبويب 1: المعاينة ----------
    with tab1:
        col1, col2, col3 = st.columns(3)
        col1.metric(t("rows"), len(df))
        col2.metric(t("cols"), len(df.columns))
        col3.metric(t("missing"), int(df.isna().sum().sum()))
        st.dataframe(df.head(50), use_container_width=True)

    # ---------- التبويب 2: التحليل ----------
    with tab2:
        st.subheader(t("missing_per_col"))
        st.dataframe(df.isna().sum().rename(t("missing_count")))
        if numeric_cols:
            st.subheader(t("num_stats"))
            st.dataframe(df[numeric_cols].describe())
        else:
            st.info(t("no_numeric"))

    # ---------- التبويب 3: الرسوم ----------
    with tab3:
        if not numeric_cols:
            st.info(t("need_numeric"))
        else:
            chart_keys = ["bar", "line", "pie"]
            chart_labels = [t("chart_" + k) for k in chart_keys]
            chart_type = chart_keys[chart_labels.index(st.selectbox(t("chart_type"), chart_labels))]
            x_col = st.selectbox(t("x_col"), df.columns.tolist())
            y_col = st.selectbox(t("y_col"), numeric_cols)

            if chart_type == "bar":
                fig = px.bar(df, x=x_col, y=y_col)
            elif chart_type == "line":
                fig = px.line(df, x=x_col, y=y_col)
            else:
                fig = px.pie(df, names=x_col, values=y_col)
            st.plotly_chart(fig, use_container_width=True)

    # ---------- التبويب 4: الملخص الذكي ----------
    with tab4:
        # الملخصات بتتحفظ في ملف summaries.json جنب app.py، فمبتتمسحش
        if "summaries" not in st.session_state:
            st.session_state.summaries = load_summaries()
        summaries = st.session_state.summaries
        for k, v in list(summaries.items()):
            if isinstance(v, str):  # تحويل الصيغة القديمة
                f_name, _, t_name = k.partition("|")
                summaries[k] = {"table": t_name.strip() or k, "file": f_name.strip(), "text": v}

        sum_key = f"{file.name} | {table_name}"
        current = summaries.get(sum_key)

        collapsed_set = st.session_state.setdefault("collapsed_summaries", set())
        is_collapsed = sum_key in collapsed_set

        if ui_rtl():
            fold_col, del_col, title_col = st.columns([1, 1, 12], vertical_alignment="center")
        else:
            title_col, fold_col, del_col = st.columns([12, 1, 1], vertical_alignment="center")
        title_col.subheader(t("summary_title", name=disp(table_name)))
        if current:
            fold_col.button(
                ":material/expand_more:" if is_collapsed else ":material/expand_less:",
                key="fold_summary",
                help=t("fold_open") if is_collapsed else t("fold_close"),
                on_click=toggle_summary, args=(sum_key,),
            )
            del_col.button(
                "🗑", key="del_summary", help=t("del_summary"),
                on_click=delete_summary, args=(sum_key,),
            )

        if not api_key:
            st.warning(t("need_key"))

        if st.button(t("btn_rewrite") if current else t("btn_write"), disabled=not api_key):
            facts = t(
                "facts",
                n=len(df),
                dtypes=df.dtypes.to_string(),
                missing=df.isna().sum().to_string(),
                stats=df[numeric_cols].describe().to_string() if numeric_cols else t("none"),
                head=df.head(15).to_string(),
            )
            prompt = t("summary_prompt", facts=facts)

            try:
                client = genai.Client(api_key=api_key)
                with st.spinner(t("spin_summary")):
                    text = ask_gemini(client, prompt)
                summaries[sum_key] = {"table": table_name, "file": file.name, "text": text}
                save_summaries(summaries)
                collapsed_set.discard(sum_key)
                st.rerun()  # نعيد الرسم عشان زراير الطي والحذف تظهر فورًا
            except Exception as e:
                st.error(friendly_error(e))

        if current and not is_collapsed:
            st.markdown(current["text"])
            doc_title = t("summary_title", name=disp(table_name))
            doc_sub = t("doc_sub", file=file.name)
            doc_rtl = is_rtl_text(current["text"])
            d1, d2, _ = st.columns([1, 1, 3])
            saved_path = None
            try:
                if SERVER_MODE:
                    safe_name = re.sub(r'[\\/:*?"<>|]', "_", str(table_name)).strip(" .") or "summary"
                    safe_download_button(
                        d1, t("save_word"),
                        data=summary_to_docx(doc_title, doc_sub, current["text"], rtl=doc_rtl),
                        file_name=f"{safe_name}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                    safe_download_button(
                        d2, t("save_pdf"),
                        data=summary_to_pdf(doc_title, doc_sub, current["text"], rtl=doc_rtl),
                        file_name=f"{safe_name}.pdf",
                        mime="application/pdf",
                    )
                else:
                    if d1.button(t("save_word"), key="save_word"):
                        saved_path = save_to_downloads(
                            summary_to_docx(doc_title, doc_sub, current["text"], rtl=doc_rtl),
                            table_name, "docx",
                        )
                    if d2.button(t("save_pdf"), key="save_pdf"):
                        saved_path = save_to_downloads(
                            summary_to_pdf(doc_title, doc_sub, current["text"], rtl=doc_rtl),
                            table_name, "pdf",
                        )
            except Exception as e:
                st.info(
                    t("install_libs") + "\n\n"
                    "python -m pip install python-docx reportlab arabic-reshaper python-bidi\n\n"
                    f"({t('details')}: {e})"
                )
            if saved_path:
                st.success(t("saved_ok", name=saved_path.name))

        others = {k: v for k, v in summaries.items() if k != sum_key}
        if others:
            open_set = st.session_state.setdefault("open_saved", set())
            with st.expander(t("others_exp", n=len(others))):
                for k, v in others.items():
                    is_open = k in open_set
                    icon = ":material/expand_less:" if is_open else ":material/expand_more:"
                    wide_button(
                        f"{icon}  {disp(v['table'])}",
                        key=f"open_{k}",
                        on_click=toggle_saved,
                        args=(k,),
                    )
                    if is_open:
                        st.caption(t("other_from", table=disp(v["table"]), file=v["file"]))
                        st.markdown(v["text"])
                        st.button(
                            "🗑", key=f"delsum_{k}", help=t("del_summary"),
                            on_click=delete_summary, args=(k,),
                        )
                        st.divider()

    # ---------- التبويب 5: الدردشة مع البيانات ----------
    with tab5:
        st.markdown(CHAT_CSS, unsafe_allow_html=True)
        st.subheader(t("chat_title"))
        st.caption(t("chat_hint"))

        if "messages" not in st.session_state:
            st.session_state.messages = []

        if st.button(t("clear_chat")):
            st.session_state.messages = []

        # حاوية للمحادثة، وخانة السؤال بتيجي بعدها تحت
        chat_box = st.container()
        prompt = st.chat_input(t("chat_input"), accept_audio=True)
        question, audio = None, None
        if prompt:
            if isinstance(prompt, str):
                question = prompt
            elif hasattr(prompt, "get"):
                question, audio = prompt.get("text"), prompt.get("audio")
            else:
                question = getattr(prompt, "text", None)
                audio = getattr(prompt, "audio", None)

        with chat_box:
            # عرض المحادثة السابقة (كل رسالة جنبها زرار نسخ وحذف بيظهروا لما تقفي عليها)
            for m in st.session_state.messages:
                render_message(m)

            if audio is not None and not question:
                if not api_key:
                    st.warning(t("need_key_short"))
                else:
                    try:
                        with st.spinner(t("spin_listen")):
                            question = transcribe(genai.Client(api_key=api_key), audio)
                    except Exception as e:
                        st.error(friendly_error(e))

            if question and not api_key:
                st.warning(t("need_key_short"))
            elif question:
                st.session_state.messages.append(
                    {"id": uuid.uuid4().hex, "role": "user", "content": question}
                )
                with st.chat_message("user"):
                    st.markdown(question)

                with st.chat_message("assistant"):
                    try:
                        client = genai.Client(api_key=api_key)
                        code_prompt = t(
                            "code_prompt",
                            dtypes=df.dtypes.to_string(),
                            head=df.head(5).to_string(),
                            question=question,
                        )

                        result, error = None, None
                        with st.spinner(t("spin_think")):
                            for attempt in range(2):
                                code = clean_code(ask_gemini(client, code_prompt))
                                try:
                                    result = run_code(code, df)
                                    error = None
                                    break
                                except Exception as e:
                                    error = str(e)
                                    code_prompt += t("fix_code", error=error)

                        if error:
                            answer = t("calc_fail")
                        else:
                            answer_prompt = t(
                                "answer_prompt", question=question, result=result_to_text(result)
                            )
                            try:
                                answer = ask_gemini(client, answer_prompt)
                            except Exception:
                                # الحصة خلصت؟ نعرض النتيجة المحسوبة من غير صياغة
                                answer = t("result_label") + "\n\n```\n" + result_to_text(result) + "\n```"

                        st.session_state.messages.append(
                            {"id": uuid.uuid4().hex, "role": "assistant", "content": answer}
                        )
                        st.rerun()  # نعيد الرسم عشان أزرار النسخ والحذف تظهر
                    except Exception as e:
                        if type(e).__name__ in ("RerunException", "StopException"):
                            raise
                        st.error(friendly_error(e))
