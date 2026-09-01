import os
import re
import io
import pdfplumber
import pandas as pd
import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# Check configuration parameters
if "OPENAI_API_KEY" not in st.secrets or "COMPANY_PASSWORD" not in st.secrets:
    st.error("System configuration missing. Check Streamlit Secrets.")
    st.stop()

openai_api_key = st.secrets["OPENAI_API_KEY"]
correct_password = st.secrets["COMPANY_PASSWORD"]

# --- LOGIN SCREEN WORKFLOW FOR STAFF ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.set_page_config(page_title="Company Login", layout="centered")
    st.title("🔒 Company Logistics Portal")
    st.write("Please enter your corporate access password to launch the interface.")
    
    user_password = st.text_input("Enter Password", type="password")
    if st.button("Login", type="primary", use_container_width=True):
        if user_password == correct_password:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("❌ Incorrect password. Access Denied.")
    st.stop()

# --- MAIN APP LOGIC ---
st.set_page_config(page_title="Liner Quotes Table", layout="wide") # Forced wide layout for spreadsheets

col1, col2 = st.columns(2)
with col1:
    st.title("🚢 Liner Quote Portal")
with col2:
    if st.button("Log Out"):
        st.session_state["authenticated"] = False
        st.rerun()

def extract_text_from_pdf(file_object):
    text = ""
    try:
        with pdfplumber.open(file_object) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        st.error(f"Error decoding PDF: {e}")
    return text.strip()

def extract_text_from_excel(file_object):
    df = pd.read_excel(file_object, sheet_name=None)
    combined_text = ""
    for sheet_name, sheet_df in df.items():
        combined_text += f"--- Sheet: {sheet_name} ---\n"
        combined_text += sheet_df.to_string(index=False) + "\n"
    return combined_text.strip()

st.subheader("➕ Step 1: Upload Quotation File")
uploaded_file = st.file_uploader("Choose a PDF or Excel file", type=["pdf", "xlsx"])

if uploaded_file is not None:
    filename = uploaded_file.name
    st.success(f"Selected file: `{filename}`")
    
    valid_file_pattern = re.compile(r"^([a-zA-Z0-9]+)(\d{4})([a-zA-Z]+)\.(pdf|xlsx)$")
    match = valid_file_pattern.match(filename)
    
    if not match:
        st.error("❌ Invalid filename! Rename your file like `Maersk2026Jun.pdf` before uploading.")
    else:
        liner = match.group(1)
        year = match.group(2)
        month = match.group(3)
        
        st.markdown("---")
        st.subheader("🔍 Step 2: Confirm & Query")
        st.info(f"📋 Detected Properties:\n* **Liner:** {liner}\n* **Year:** {year}\n* **Month:** {month}")
        
        if st.button("Extract Standardized Data", type="primary", use_container_width=True):
            with st.spinner("AI standardizing layout into table structure..."):
                try:
                    if filename.endswith(".pdf"):
                        raw_content = extract_text_from_pdf(uploaded_file)
                    else:
                        raw_content = extract_text_from_excel(uploaded_file)
                    
                    if not raw_content:
                        st.error("❌ Critical: No text content could be decoded.")
                        st.stop()
                    
                    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
                    
                    # Force AI to return data in a single row string mapping perfectly to your wide layout columns
                    prompt = ChatPromptTemplate.from_messages([
                        ("system", (
                            "You are an expert logistics analyst. Convert messy shipping quotes into a single text row.\n"
                            "You MUST respond ONLY with a clean single row using a semicolon (;) as a separator. "
                            "Do not write any introductory or concluding sentences. Do not use markdown backticks.\n\n"
                            "The format must follow this exact output structure:\n"
                            "[Ocean Freight Rate (USD)];[OTHC];[DTHC];[BAF];[Documentation Fee];[Peak Season Surcharge (PSS)];[Estimated Transit Time (Days)];[Validity Period]\n\n"
                            "Rules:\n- Extract values carefully.\n- Use 'Not Mentioned' if data is missing."
                        )),
                        ("user", "{document_text}")
                    ])
                    
                    chain = prompt | llm
                    response = chain.invoke({"document_text": raw_content})
                    
                    row_data = response.content.strip().split(";")
                    
                    # Define full database columns including tracking metadata properties
                    headers = [
                        "File Name", "Liner", "Year", "Month", 
                        "Ocean Freight Rate (USD)", "Origin THC (OTHC)", "Destination THC (DTHC)", 
                        "Bunker Surcharge (BAF)", "Documentation Fee", "Peak Season Surcharge (PSS)", 
                        "Transit Time (Days)", "Validity Period"
                    ]
                    
                    # Build row content array tracking all extra metrics
                    full_row = [filename, liner, year, month] + row_data
                    
                    # Handle safety slice alignment anomalies
                    if len(full_row) > len(headers):
                        full_row = full_row[:len(headers)]
                    elif len(full_row) < len(headers):
                        full_row += ["Not Mentioned"] * (len(headers) - len(full_row))
                    
                    df_result = pd.DataFrame([full_row], columns=headers)
                    
                    st.success("Extraction Complete!")
                    st.subheader("📋 Standardized Logistical Record Row")
                    
                    # Render full horizontal spreadsheet row block display
                    st.dataframe(df_result, use_container_width=True, hide_index=True)
                    
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        df_result.to_excel(writer, index=False, sheet_name='QuotationData')
                    
                    excel_data = excel_buffer.getvalue()
                    
                    st.download_button(
                        label="📥 Download Row as Excel Spreadsheet",
                        data=excel_data,
                        file_name=f"{liner}_{year}_{month}_Record.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                        
                except Exception as e:
                    st.error(f"Error parsing file elements: {e}")
