import os
import re
import pandas as pd
import streamlit as st
from pypdf import PdfReader
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# Securely check for your OpenAI key
if "OPENAI_API_KEY" not in st.secrets:
    st.error("Missing API Key! Please add your OPENAI_API_KEY to Streamlit Secrets.")
    st.stop()

openai_api_key = st.secrets["OPENAI_API_KEY"]

PREDETERMINED_FORMAT = """
1. Ocean Freight Rate (USD):
2. Origin Terminal Handling Charges (OTHC):
3. Destination Terminal Handling Charges (DTHC):
4. Bunker Adjustment Factor (BAF):
5. Documentation Fee:
6. Peak Season Surcharge (PSS):
7. Estimated Transit Time (Days):
8. Validity Period:
"""

def extract_text_from_pdf(file_object):
    text = ""
    reader = PdfReader(file_object)
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def extract_text_from_excel(file_object):
    df = pd.read_excel(file_object, sheet_name=None)
    combined_text = ""
    for sheet_name, sheet_df in df.items():
        combined_text += f"--- Sheet: {sheet_name} ---\n"
        combined_text += sheet_df.to_string(index=False) + "\n"
    return combined_text

st.set_page_config(page_title="Liner Quotes", layout="centered")
st.title("🚢 Mobile Liner Quote Interface")
st.write("Upload a quote from your phone storage to run a standardized query.")

st.subheader("➕ Step 1: Upload Quotation File")
uploaded_file = st.file_uploader("Choose a PDF or Excel file", type=["pdf", "xlsx"])

if uploaded_file is not None:
    filename = uploaded_file.name
    st.success(f"Selected file: `{filename}`")
    
    # Check if file name matches our strict naming layout
    valid_file_pattern = re.compile(r"^([a-zA-Z0-9]+)(\d{4})([a-zA-Z]+)\.(pdf|xlsx)$")
    match = valid_file_pattern.match(filename)
    
    if not match:
        st.error("❌ Invalid filename! Rename your file like `Maersk2026Jun.pdf` or `ONE2026Jul.xlsx` before uploading.")
    else:
        liner = match.group(1)
        year = match.group(2)
        month = match.group(3)
        
        st.markdown("---")
        st.subheader("🔍 Step 2: Confirm & Query")
        st.info(f"📋 Detected Properties:\n* **Liner:** {liner}\n* **Year:** {year}\n* **Month:** {month}")
        
        if st.button("Extract Standardized Data", type="primary", use_container_width=True):
            with st.spinner("AI reading file layout..."):
                try:
                    if filename.endswith(".pdf"):
                        raw_content = extract_text_from_pdf(uploaded_file)
                    else:
                        raw_content = extract_text_from_excel(uploaded_file)
                    
                    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
                    
                    prompt = ChatPromptTemplate.from_messages([
                        ("system", (
                            "You are an expert logistics analyst. Convert messy shipping quotes into a strict format.\n\n"
                            f"REQUIRED FORMAT:\n{PREDETERMINED_FORMAT}\n"
                            "Rules:\n- Never alter heading names.\n- Use 'Not Mentioned' if data is missing."
                        )),
                        ("user", "{document_text}")
                    ])
                    
                    chain = prompt | llm
                    response = chain.invoke({"document_text": raw_content})
                    
                    st.success("Extraction Complete!")
                    st.code(response.content, language="markdown")
                    
                except Exception as e:
                    st.error(f"Error parsing file: {e}")
