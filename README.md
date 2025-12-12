# Healthcare Claims PDF Extractor & Validator

This project is a Python-based tool designed to extract, validate, and classify healthcare claim records from PDF files.  
It simulates a real-world workflow used by health insurance and medical billing systems, where incoming claims must be checked for accuracy before processing.

The tool performs:
- PDF table extraction  
- Field-level validation  
- Health card MOD10 (Luhn) check  
- Date validation  
- Error reporting  
- Output file generation  

---

## 🚀 Features

### ✔ PDF Data Extraction
- Extracts structured tabular data from multi-page PDF files using **pdfplumber**.

### ✔ Validation Logic
The script validates each field according to realistic healthcare rules:

#### **Health Card Number**
- Required  
- Must be **10 digits**  
- Must be **numeric**  
- Must pass the **Luhn (MOD10)** checksum  

#### **Version Code**
- Required  
- Must be **2 uppercase letters (A–Z)**  

#### **Date of Birth**
- Must be a valid date  
- Cannot be in the future  
- Patient age must be **0–150**  

#### **Service Date**
- Must be a valid date  
- Cannot be in the future  
- Cannot be earlier than the Date of Birth  
- Cannot be earlier than **6 months before today**  

---

## 📂 Project Structure



## 🛠 Installation

Make sure Python 3.7+ is installed, then install the required dependency:

```bash
pip install pdfplumber

python3 -m pip install pdfplumber


## ▶️ Usage

Run the script:

```bash
python Health_system.py patient_records_test.pdf
```

Or specify custom outputs:

```bash
python Health_system.py patient_records_test.pdf \
    --valid_csv valid_records.csv \
    --error_report error_report.txt
```
## 📤 Output Files

### valid_records.csv
Contains normalized valid patient claim records.

### error_report.txt
Includes error details for invalid records and summary statistics.

