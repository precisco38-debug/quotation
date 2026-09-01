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
st.set_page_config(page_title="Liner Quotes Table", layout="wide")

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
                    
                    # Unified extraction format template request block
                    prompt = ChatPromptTemplate.from_messages([
                        ("system", (
                            "You are an expert logistics analyst. Convert messy shipping quotes into a strict layout.\n"
                            "You MUST respond ONLY with a clean semicolon (;) separated string format using this text profile template structure:\n"
                            "Ocean Freight Rate (USD);[parsed value]\n"
                            "Origin Terminal Handling Charges (OTHC);[parsed value]\n"
                            "Destination Terminal Handling Charges (DTHC);[parsed value]\n"
                            "Bunker Adjustment Factor (BAF);[parsed value]\n"
                            "Documentation Fee;[parsed value]\n"
                            "Peak Season Surcharge (PSS);[parsed value]\n"
                            "Estimated Transit Time (Days);[parsed value]\n"
                            "Validity Period;[parsed value]\n\n"
                            "Rules:\n- Never alter heading names.\n- Use 'Not Mentioned' if data is missing."
                        )),
                        ("user", "{document_text}")
                    ])
                    
                    chain = prompt | llm
                    response = chain.invoke({"document_text": raw_content})
                    
                    csv_lines = [line.split(";") for line in response.content.strip().split("\n") if ";" in line]
                    
                    if csv_lines:
                        # 1. Build a Vertical Mobile-Friendly Table Block Structure
                        df_vertical = pd.DataFrame(csv_lines, columns=["Metric", "Extracted Value"])
                        
                        st.success("Extraction Complete!")
                        st.subheader("📋 1. Mobile Vertical View")
                        st.dataframe(df_vertical, use_container_width=True, hide_index=True)
                        
                        # 2. Build a Wide Horizontal Row Layout Spreadsheet Block
                        horiz_headers = ["File Name", "Liner", "Year", "Month"] + [row[0] for row in csv_lines]
                        horiz_values = [filename, liner, year, month] + [row[1] for row in csv_lines]
                        df_horizontal = pd.DataFrame([horiz_values], columns=horiz_headers)
                        
                        st.subheader("📋 2. PC Horizontal Spreadsheet Record View")
                        st.dataframe(df_horizontal, use_container_width=True, hide_index=True)
                        
                        # 3. Export to Excel File Action Logic
                        excel_buffer = io.BytesIO()
                        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                            df_horizontal.to_excel(writer, index=False, sheet_name='QuotationData')
                        excel_data = excel_buffer.getvalue()
                        
                        st.download_button(
                            label="📥 Download Record as Excel Spreadsheet File",
                            data=excel_data,
                            file_name=f"{liner}_{year}_{month}_Record.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                    else:
                        st.error("AI returned faulty processing blocks. Try re-clicking the extraction button.")
                        
                except Exception as e:
                    st.error(f"Error parsing file elements: {e}")
