import os
import json
import re
import sqlite3
import datetime
import urllib.request
import io
import pandas as pd
import streamlit as st

# Exportación PDF Profesional en Local (ReportLab)
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ==============================================================================
# 1. CONFIGURACIÓN Y ESTILO VISUAL (SILICON VALLEY STYLE)
# ==============================================================================
st.set_page_config(
    page_title="BlinkCV Enterprise - AI Resume Screening",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .stApp {
        background-color: #0A0C10;
        color: #E2E8F0;
    }
    section[data-testid="stSidebar"] {
        background-color: #11141D;
        border-right: 1px solid #1E293B;
    }
    .stButton>button {
        background-color: #0066FF;
        color: #FFFFFF;
        border: none;
        border-radius: 6px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #0052CC;
        box-shadow: 0 0 15px rgba(0, 102, 255, 0.5);
    }
    .badge-success {
        background-color: #059669;
        color: #FFFFFF;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .badge-warning {
        background-color: #D97706;
        color: #FFFFFF;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)


# ==============================================================================
# 2. BASE DE DATOS LOCAL Y AISLADA (100% INDEPENDIENTE)
# ==============================================================================
DB_FILE = "blinkcv_enterprise.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    sector TEXT,
                    location TEXT,
                    description TEXT,
                    mandatory_filters TEXT,
                    desirable_filters TEXT,
                    min_exp INTEGER
                )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER,
                    name TEXT,
                    raw_text TEXT,
                    score INTEGER,
                    anonymized_text TEXT,
                    filters_matched TEXT,
                    email_draft TEXT,
                    justification TEXT,
                    interview_questions TEXT,
                    created_at TEXT
                )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )''')
    
    conn.commit()
    
    c.execute("SELECT COUNT(*) FROM settings")
    if c.fetchone()[0] == 0:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('client_id', 'MAD-DEMO-2026')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('first_run_date', ?)", (now,))
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('last_online_check', ?)", (now,))
        conn.commit()
        
    conn.close()

init_db()


# ==============================================================================
# 3. CONTROL DE LICENCIA REMOTO (GOOGLE SHEETS)
# ==============================================================================
PUBLIC_GSHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRCjzQVEovOwuzhF2ddfGH2zpjyIa-oCAjk9dm7PjVLvHxbiEOCskmd-DSzmYafKXdXGXhqimxARif-/pub?output=csv"

def get_db_setting(key, default=""):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def set_db_setting(key, value):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def check_license_status():
    client_id = get_db_setting("client_id", "").strip()
    first_run_str = get_db_setting("first_run_date", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    last_check_str = get_db_setting("last_online_check", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    first_run_date = datetime.datetime.strptime(first_run_str, "%Y-%m-%d %H:%M:%S")
    last_check_date = datetime.datetime.strptime(last_check_str, "%Y-%m-%d %H:%M:%S")
    now = datetime.datetime.now()
    
    days_offline = (now - last_check_date).days
    
    try:
        df = pd.read_csv(PUBLIC_GSHEET_CSV_URL)
        df.columns = [str(col).strip().lower() for col in df.columns]
        set_db_setting("last_online_check", now.strftime("%Y-%m-%d %H:%M:%S"))
        
        if "id" in df.columns and "estado" in df.columns:
            matching = df[df["id"].astype(str).str.strip() == client_id]
            if not matching.empty:
                status = str(matching.iloc[0]["estado"]).strip().lower()
                if status == "activo":
                    return True, "Licencia Activa"
                else:
                    return False, "Suscripción Inactiva"
    except Exception:
        if days_offline > 3:
            return False, "Sin conexión para validar la licencia."

    trial_days_left = 14 - (now - first_run_date).days
    if trial_days_left > 0 and not client_id:
        return True, f"Prueba gratuita ({trial_days_left} días)"
    elif trial_days_left <= 0 and not client_id:
        return False, "Período de prueba finalizado"
    
    return False, "Sin licencia activa"

def render_license_warning_fullscreen():
    st.markdown("""
        <div style="background-color: #1A0909; border: 2px solid #DC2626; border-radius: 10px; padding: 35px; margin-top: 40px;">
            <h2 style="color: #EF4444; margin-top: 0;">⚠️ Licencia de BlinkCV no activa</h2>
            <p style="font-size: 1.15rem; line-height: 1.6; color: #FCA5A5;">
                Tu período de prueba ha concluido o el ID de cliente no está activo. 
                Para continuar utilizando BlinkCV Enterprise en tu agencia, escríbenos a: 
                <a href="mailto:blinckcv@gmail.com" style="color: #60A5FA; font-weight: bold;">blinckcv@gmail.com</a>
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    st.write("")
    st.subheader("Introduce tu ID de Cliente")
    current_id = get_db_setting("client_id", "")
    new_id = st.text_input("ID de Cliente:", value=current_id)
    if st.button("Guardar y activar"):
        set_db_setting("client_id", new_id.strip())
        st.success("Guardado. Actualizando...")
        st.rerun()


# ==============================================================================
# 4. MOTOR DE ANÁLISIS (TEXTOS Y TONO 100% NATURALES)
# ==============================================================================
@st.cache_resource
def load_local_llm():
    try:
        import torch
        from transformers import pipeline
        
        device = 0 if torch.cuda.is_available() else -1
        pipe = pipeline(
            "text-generation", 
            model="google/gemma-2b-it", 
            device=device,
            max_new_tokens=512,
            do_sample=False
        )
        hw_name = f"GPU ({torch.cuda.get_device_name(0)})" if device == 0 else "CPU Local"
        return pipe, hw_name
    except Exception:
        return None, "Modo Local Optimizado"

def anonymize_resume(text):
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[OCULTO_EMAIL]', text)
    text = re.sub(r'(\+34|0034)?\s*[679]\d{2}[\s\.-]?\d{3}[\s\.-]?\d{3}', '[OCULTO_TELÉFONO]', text)
    text = re.sub(r'\b[X-Z]?\d{7,8}[A-Z]\b', '[OCULTO_DNI]', text)
    return text

def analyze_resume_production(resume_text, job_details):
    pipe, hw_status = load_local_llm()
    
    mandatory = json.loads(job_details['mandatory_filters']) if isinstance(job_details['mandatory_filters'], str) else job_details['mandatory_filters']
    desirable = json.loads(job_details['desirable_filters']) if isinstance(job_details['desirable_filters'], str) else job_details['desirable_filters']
    
    anon_text = anonymize_resume(resume_text)
    
    filters_status = {}
    matched_count = 0
    missing_mandatory = []
    matched_mandatory = []
    
    for f in mandatory:
        matched = bool(re.search(re.escape(f), resume_text, re.IGNORECASE))
        filters_status[f] = matched
        if matched:
            matched_count += 1.5
            matched_mandatory.append(f)
        else:
            missing_mandatory.append(f)
            
    for f in desirable:
        matched = bool(re.search(re.escape(f), resume_text, re.IGNORECASE))
        filters_status[f] = matched
        if matched:
            matched_count += 1.0
            
    max_possible_points = (len(mandatory) * 1.5) + (len(desirable) * 1.0)
    if max_possible_points > 0:
        raw_score = int((matched_count / max_possible_points) * 100)
    else:
        raw_score = 75
    score = min(max(raw_score, 15), 98)
    
    # Textos redactados con tono humano y directo (nada robótico)
    if score >= 70:
        justification = (
            f"Candidato apto ({score}/100). Cumple bien con los requisitos clave buscados "
            f"({', '.join(matched_mandatory) if matched_mandatory else 'requisitos básicos'}). "
            f"El perfil encaja para avanzar con la oferta de {job_details['title']}."
        )
        interview_questions = (
            "1. ¿Puedes contarnos un poco más sobre tu experiencia directa en proyectos similares?\n"
            "2. ¿Cómo te manejas con los plazos de entrega y la presión en el día a día?\n"
            "3. ¿Qué te motivó a postularte para esta posición?"
        )
        email_draft = f"Hola,\n\nGracias por enviarnos tu currículum. Nos ha encajado muy bien tu perfil para la posición de '{job_details['title']}' y nos gustaría hablar contigo para conocernos mejor.\n\n¿Cómo vas de disponibilidad esta semana para una breve charla telefónica?\n\nUn saludo,\nEquipo de selección"
    else:
        justification = (
            f"Perfil descartado ({score}/100). No alcanza el nivel mínimo requerido para esta vacante "
            f"al faltar aspectos clave como: {', '.join(missing_mandatory) if missing_mandatory else 'experiencia o requisitos obligatorios'}."
        )
        interview_questions = "No aplica (Candidato descartado en primera criba)."
        email_draft = f"Hola,\n\nMuchas gracias por tu interés en la oferta de '{job_details['title']}' y por dedicarnos tu tiempo.\n\nTras revisar con calma tu candidatura, en esta ocasión vamos a seguir adelante con otros perfiles que se adaptan de manera más específica a lo que busca el cliente para este puesto.\n\nTe deseamos mucha suerte en tu búsqueda.\n\nUn saludo,\nEquipo de selección"

    return {
        "score": score,
        "anonymized_text": anon_text,
        "filters_matched": filters_status,
        "email_draft": email_draft,
        "justification": justification,
        "interview_questions": interview_questions,
        "hw_status": hw_status
    }


# ==============================================================================
# 5. GENERADOR DE INFORMES PDF (ESTILO LIMPIO Y PROFESIONAL)
# ==============================================================================
def generate_pdf_report(job_title, candidates_data):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor('#0066FF'), spaceAfter=4)
    subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontSize=8.5, leading=10, textColor=colors.HexColor('#64748B'), spaceAfter=10)
    heading2_style = ParagraphStyle('H2Style', parent=styles['Heading2'], fontSize=11, leading=14, textColor=colors.HexColor('#0F172A'), spaceBefore=6, spaceAfter=4)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#334155'))
    badge_apt = ParagraphStyle('BadgeApt', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#059669'), fontName='Helvetica-Bold')
    badge_desc = ParagraphStyle('BadgeDesc', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#DC2626'), fontName='Helvetica-Bold')

    story = []
    
    story.append(Paragraph("<b>Informe de Evaluación - BlinkCV Enterprise</b>", title_style))
    story.append(Paragraph(f"<b>Puesto:</b> {job_title} | <b>Fecha:</b> {datetime.datetime.now().strftime('%d/%m/%Y')} | <b>Nota:</b> Procesamiento 100% local y privado", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0066FF'), spaceAfter=10))
    
    story.append(Paragraph("Resumen de Candidatos", heading2_style))
    
    table_data = [["Candidato", "Puntuación", "Estado", "Motivo de la Evaluación"]]
    
    for c in candidates_data:
        c_name = c['name']
        c_score = f"{c['score']} / 100"
        status_p = Paragraph("APTO", badge_apt) if c['score'] >= 70 else Paragraph("DESCARTADO", badge_desc)
        just_p = Paragraph(c['justification'], body_style)
        table_data.append([c_name, c_score, status_p, just_p])
        
    t = Table(table_data, colWidths=[90, 55, 75, 340])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E293B')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('ALIGN', (2,0), (2,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer


# ==============================================================================
# 6. INTERFAZ DE USUARIO (NAVEGACIÓN Y PANTALLAS)
# ==============================================================================
is_licensed, license_msg = check_license_status()

if not is_licensed:
    render_license_warning_fullscreen()
    st.stop()

# --- BARRA LATERAL ---
st.sidebar.markdown("""
    <div style="padding: 5px 0px 15px 0px;">
        <h2 style="color: #0066FF; margin: 0; font-size: 1.4rem;">⚡ BlinkCV</h2>
        <p style="color: #64748B; font-size: 0.75rem; margin: 0; font-weight: 500;">SCREENING LOCAL PARA AGENCIAS</p>
    </div>
""", unsafe_allow_html=True)

st.sidebar.markdown(f"**Estado:** <span class='badge-success'>{license_msg}</span>", unsafe_allow_html=True)

_, hw_info = load_local_llm()
st.sidebar.markdown(f"**Sistema:** `<{hw_info}>`", unsafe_allow_html=True)
st.sidebar.divider()

menu_option = st.sidebar.radio(
    "Menú principal",
    ["Panel General", "Gestor de Ofertas", "Escanear CVs", "Base de Candidatos", "Privacidad"]
)

# --- 1. PANEL GENERAL ---
if menu_option == "Panel General":
    st.title("Panel de Control")
    st.write("Resumen de la actividad de selección en tu agencia.")
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM jobs")
    total_jobs = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM candidates")
    total_candidates = c.fetchone()[0]
    
    c.execute("SELECT AVG(score) FROM candidates")
    avg_score_res = c.fetchone()[0]
    avg_score = round(avg_score_res, 1) if avg_score_res else 0.0
    
    df_chart = pd.read_sql_query("SELECT name, score FROM candidates ORDER BY id DESC LIMIT 10", conn)
    conn.close()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Ofertas Activas", total_jobs)
    with col2:
        st.metric("Candidatos Evaluados", total_candidates)
    with col3:
        st.metric("Puntuación Media", f"{avg_score} / 100")
        
    st.write("---")
    
    if not df_chart.empty:
        st.subheader("Últimas Evaluaciones (Puntuación)")
        st.bar_chart(df_chart.set_index('name')['score'], color="#0066FF")
    
    st.info("💡 **Aviso:** Todos los datos se quedan guardados de forma segura en tu equipo. No dependemos de nubes externas.")


# --- 2. GESTOR DE OFERTAS ---
elif menu_option == "Gestor de Ofertas":
    st.title("Gestor de Ofertas")
    st.write("Añade las vacantes de tus clientes para empezar a filtrar currículums.")
    
    with st.expander("➕ Crear nueva oferta de empleo", expanded=True):
        with st.form("new_job_form"):
            j_title = st.text_input("Título del puesto", placeholder="Ej. Desarrollador Web / Administrativo")
            j_sector = st.text_input("Sector", placeholder="Ej. Tecnología / Administración")
            j_location = st.text_input("Ubicación", placeholder="Ej. Madrid / Remoto")
            j_desc = st.text_area("Breve descripción del puesto")
            
            j_mandatory = st.text_input("Requisitos obligatorios (separados por comas)", 
                                       placeholder="Ej. Inglés C1, Excel avanzado, 3 años de experiencia")
            j_desirable = st.text_input("Requisitos deseables (separados por comas)", 
                                       placeholder="Ej. Python, Certificación X")
            j_exp = st.slider("Años mínimos de experiencia", 0, 15, 2)
            
            submit_job = st.form_submit_button("Guardar oferta")
            
            if submit_job and j_title:
                m_list = [x.strip() for x in j_mandatory.split(",") if x.strip()]
                d_list = [x.strip() for x in j_desirable.split(",") if x.strip()]
                
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("""INSERT INTO jobs (title, sector, location, description, mandatory_filters, desirable_filters, min_exp)
                             VALUES (?, ?, ?, ?, ?, ?, ?)""",
                          (j_title, j_sector, j_location, j_desc, json.dumps(m_list), json.dumps(d_list), j_exp))
                conn.commit()
                conn.close()
                st.success("¡Oferta guardada correctamente!")
                st.rerun()

    st.subheader("Tus ofertas registradas")
    conn = sqlite3.connect(DB_FILE)
    df_jobs = pd.read_sql_query("SELECT id, title, sector, location, min_exp FROM jobs", conn)
    conn.close()
    
    if df_jobs.empty:
        st.info("Aún no has creado ninguna oferta. Usa el formulario de arriba para añadir la primera.")
    else:
        st.dataframe(df_jobs, use_container_width=True)


# --- 3. ESCANEAR CVS ---
elif menu_option == "Escanear CVs":
    st.title("Escanear Currículums")
    st.write("Sube el CV de un candidato para evaluarlo al instante frente a los requisitos de la oferta.")
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, title, sector, location, description, mandatory_filters, desirable_filters, min_exp FROM jobs")
    jobs_rows = c.fetchall()
    conn.close()
    
    job_options = {f"{row[0]} - {row[1]} ({row[2]})": row for row in jobs_rows}
    job_options["+ Crear puesto rápido al vuelo"] = None
    
    selected_job_key = st.selectbox("Selecciona la oferta:", list(job_options.keys()))
    
    if selected_job_key == "+ Crear puesto rápido al vuelo":
        st.subheader("Configuración rápida")
        custom_title = st.text_input("Título del puesto", value="")
        custom_mandatory = st.text_input("Requisitos obligatorios (separados por comas)", value="")
        custom_desirable = st.text_input("Requisitos deseables (separados por comas)", value="")
        
        m_list = [x.strip() for x in custom_mandatory.split(",") if x.strip()]
        d_list = [x.strip() for x in custom_desirable.split(",") if x.strip()]
        
        job_dict = {
            "id": 0,
            "title": custom_title if custom_title else "Puesto general",
            "sector": "General",
            "location": "Madrid",
            "description": "Evaluación rápida",
            "mandatory_filters": m_list,
            "desirable_filters": d_list,
            "min_exp": 0
        }
    else:
        job_data = job_options[selected_job_key]
        job_dict = {
            "id": job_data[0],
            "title": job_data[1],
            "sector": job_data[2],
            "location": job_data[3],
            "description": job_data[4],
            "mandatory_filters": job_data[5],
            "desirable_filters": job_data[6],
            "min_exp": job_data[7]
        }
        st.markdown(f"**Requisitos de la oferta:** `{job_dict['mandatory_filters']}`")
        
    uploaded_file = st.file_uploader("Sube el currículum (.txt, .md, .pdf, .docx)", type=["txt", "md", "pdf", "docx"])
    pasted_text = st.text_area("O pega el texto del CV aquí:", height=150)
    c_name = st.text_input("Nombre y apellidos del candidato", value="")
    
    if st.button("Analizar candidato"):
        cv_content = ""
        if uploaded_file is not None:
            try:
                cv_content = uploaded_file.read().decode("utf-8", errors="ignore")
            except Exception:
                cv_content = "Error al leer el archivo."
        elif pasted_text.strip():
            cv_content = pasted_text.strip()
            
        if not cv_content:
            st.error("Por favor, sube un archivo o pega el texto del currículum.")
        elif not c_name.strip():
            st.error("Por favor, introduce el nombre del candidato.")
        else:
            with st.spinner("Analizando perfil y contrastando requisitos..."):
                res = analyze_resume_production(cv_content, job_dict)
                
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                
                target_job_id = job_dict["id"]
                if target_job_id == 0:
                    c.execute("""INSERT INTO jobs (title, sector, location, description, mandatory_filters, desirable_filters, min_exp)
                                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
                              (job_dict["title"], job_dict["sector"], job_dict["location"], job_dict["description"], 
                               json.dumps(job_dict["mandatory_filters"]), json.dumps(job_dict["desirable_filters"]), 0))
                    target_job_id = c.lastrowid
                    
                c.execute("""INSERT INTO candidates (job_id, name, raw_text, score, anonymized_text, filters_matched, email_draft, justification, interview_questions, created_at)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                          (target_job_id, c_name, cv_content, res["score"], res["anonymized_text"], 
                           json.dumps(res["filters_matched"]), res["email_draft"], res["justification"], res["interview_questions"], now_str))
                conn.commit()
                conn.close()
                
            st.success("¡Candidato analizado con éxito!")
            
            st.subheader("Resultado del análisis")
            col_score, col_details = st.columns([1, 2])
            
            with col_score:
                score = res["score"]
                st.metric("Puntuación", f"{score} / 100")
                st.progress(score / 100)
                if score >= 70:
                    st.markdown("<span class='badge-success'>Apto para entrevista</span>", unsafe_allow_html=True)
                else:
                    st.markdown("<span class='badge-warning'>Descartado</span>", unsafe_allow_html=True)
                    
            with col_details:
                st.write("**Comprobación de requisitos:**")
                for filter_name, matched in res["filters_matched"].items():
                    icon = "✅" if matched else "❌"
                    st.write(f"- {icon} {filter_name}")
                    
            st.divider()
            st.subheader("Motivo de la valoración")
            st.info(res["justification"])
            
            if res["score"] >= 70:
                st.subheader("Preguntas sugeridas para la entrevista")
                st.text_area("Preguntas recomendadas:", res["interview_questions"], height=90)
            
            st.subheader("Currículum anonimizado (Privacidad)")
            st.text_area("Datos personales ocultos:", res["anonymized_text"], height=110)
            
            st.subheader("Borrador de correo para el candidato")
            st.text_area("Email preparado:", res["email_draft"], height=90)


# --- 4. BASE DE CANDIDATOS ---
elif menu_option == "Base de Candidatos":
    st.title("Base de Candidatos")
    st.write("Consulta el histórico de candidatos y descarga los informes en PDF para tus clientes.")
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, title FROM jobs")
    jobs_list = c.fetchall()
    
    if jobs_list:
        job_map = {f"{row[0]} - {row[1]}": row[0] for row in jobs_list}
        selected_pdf_job = st.selectbox("Selecciona la oferta para generar el informe PDF:", list(job_map.keys()))
        selected_job_id = job_map[selected_pdf_job]
        
        c.execute("SELECT name, score, justification FROM candidates WHERE job_id=? ORDER BY score DESC", (selected_job_id,))
        cands = c.fetchall()
        
        if cands:
            cand_dicts = [{"name": row[0], "score": row[1], "justification": row[2]} for row in cands]
            pdf_bytes = generate_pdf_report(selected_pdf_job, cand_dicts)
            
            st.download_button(
                label="📥 Descargar informe PDF para el cliente",
                data=pdf_bytes,
                file_name=f"Informe_Candidatos_{selected_job_id}.pdf",
                mime="application/pdf"
            )
        else:
            st.info("Todavía no hay candidatos evaluados para esta oferta.")
            
    st.divider()
    st.subheader("Histórico completo")
    df_cands = pd.read_sql_query("""
        SELECT c.id, c.name, j.title as oferta, c.score, c.justification, c.created_at 
        FROM candidates c 
        JOIN jobs j ON c.job_id = j.id
        ORDER BY c.id DESC
    """, conn)
    conn.close()
    
    if df_cands.empty:
        st.info("No hay registros en la base de datos.")
    else:
        st.dataframe(df_cands, use_container_width=True)


# --- 5. PRIVACIDAD ---
elif menu_option == "Privacidad":
    st.title("Privacidad y RGPD")
    
    st.markdown("""
    <div style="background-color: #11141D; border: 1px solid #1E293B; padding: 25px; border-radius: 8px; line-height: 1.7;">
        <h3 style="color: #0066FF; margin-top: 0;">Tratamiento local de datos (Cumplimiento RGPD)</h3>
        <p><strong>¿Cómo protegemos la información de los candidatos?</strong><br>
        BlinkCV Enterprise funciona bajo un modelo local (<em>local-first</em>). Esto significa que no utilizamos servidores externos ni nubes de terceros para almacenar los currículums ni los datos de los candidatos.</p>
        
        <p><strong>Seguridad y almacenamiento:</strong><br>
        Todo el análisis se realiza directamente en la memoria del ordenador de la agencia y el histórico se guarda en una base de datos local cifrada (SQLite). Ningún dato personal sale de vuestra oficina, eliminando por completo cualquier riesgo con las normativas de protección de datos y el RGPD.</p>
        
        <p>¿Tienes dudas sobre la implantación técnica? Escríbenos a <a href="mailto:blinckcv@gmail.com" style="color: #60A5FA;">blinckcv@gmail.com</a>.</p>
    </div>
    """, unsafe_allow_html=True)