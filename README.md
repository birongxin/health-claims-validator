Healthcare Claims PDF Extractor & Validator

This project is a Python-based tool designed to extract, validate, and classify healthcare claim records from PDF files.
It simulates a real-world workflow used by insurance and medical billing systems, where incoming claims must meet strict formatting and logical rules before processing.

The tool includes:

PDF table extraction

Field-level validation

Health card MOD10 (Luhn) checksum

Date validation and normalization

Record classification (valid vs invalid)

CSV + text error report generation

Features
PDF Data Extraction

Uses pdfplumber to extract structured table data from multi-page PDFs.

Validation Logic (per healthcare rules)
Health Card Number

Required

Must be 10 digits, numeric

Must pass the Luhn (MOD10) checksum

Version Code

Required

Must be 2 uppercase letters (A–Z)

Date of Birth

Must be a valid date

Cannot be in the future

Patient age must be within 0–150 years

Service Date

Must be a valid date

Cannot be in the future

Cannot be earlier than Date of Birth

Cannot be more than 6 months before today

Design Overview

The solution is structured into clear functional layers:

PDF extraction layer

Converts PDF tables into dictionaries.

Validation layer

Applies all business rules (Luhn, date logic, version code rules).

Normalization layer

Converts dates into ISO YYYY-MM-DD.

Output layer

Valid records → valid_records.csv

Invalid records + reasons → error_report.txt

CLI entrypoint

main() provides argparse-based command-line usage.

---

## Project Structure

health-claims-validator/
│── Health_system.py         # Main Python script
│── patient_records_test.pdf # Sample input PDF
│── valid_records.csv        # Generated valid records
│── error_report.txt         # Generated error report
└── README.md                # Documentation



---

🛠 Installation

Install dependency:

pip install pdfplumber

▶Usage

Run the script:

python Health_system.py patient_records_test.pdf

Example Output
valid_records.csv
PatientID,HealthCardNumber,VersionCode,DateOfBirth,ServiceDate
P001,1234567890,AB,1985-03-12,2025-01-10
P002,9876543210,CD,1990-07-25,2025-02-03

error_report.txt
ERROR REPORT
Generated: 2025-12-11 18:20:00
Total Records Processed: 7
Valid Records: 2
Invalid Records: 5

INVALID RECORDS:
Patient ID: P003
- Health card number failed MOD 10 (Luhn) validation
- Service date is more than 6 months in the past

Patient ID: P004
- Version code must be 2 uppercase letters (A–Z)
- Date of birth is not a valid date

