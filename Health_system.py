import argparse
import csv
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, date, timedelta
from typing import List, Tuple, Dict, Optional

import pdfplumber


# ==============================
# Data model
# ==============================

@dataclass
class PatientRecord:
    """
    Normalized representation of a single patient claim record.
    All dates are stored in ISO format (YYYY-MM-DD).
    """
    PatientID: str
    HealthCardNumber: str
    VersionCode: str
    DateOfBirth: str   # ISO string
    ServiceDate: str   # ISO string


# ==============================
# Utility functions
# ==============================

def luhn_check(number: str) -> bool:
    """
    Run Luhn (MOD 10) check on a numeric string.

    Expected:
        - 'number' is a string of digits (e.g., '1234567890')
        - The last digit is the check digit.

    Returns:
        True if the number passes the Luhn check, False otherwise.
    """
    if not number.isdigit():
        return False

    digits = [int(d) for d in number]
    check_digit = digits[-1]
    # Reverse all digits except the check digit
    digits = digits[:-1][::-1]

    total = 0
    for i, d in enumerate(digits):
        if i % 2 == 0:
            # Double every second digit (from the right in the original number)
            d *= 2
            if d > 9:
                d -= 9
        total += d

    return (total + check_digit) % 10 == 0


def parse_date_flex(
    date_str: str,
    field_name: str,
    errors: List[str]
) -> Optional[date]:
    """
    Try to parse a date string using multiple common formats.
    If parsing fails, an error message is appended to 'errors'.

    Supported input formats (examples):
        2024-01-31
        2024/01/31
        31-01-2024
        31/01/2024
        20240131

    Returns:
        - datetime.date if parsing succeeds.
        - None if parsing fails (and logs an error).
    """
    if not date_str or not date_str.strip():
        errors.append(f"{field_name} is empty")
        return None

    date_str = date_str.strip()

    patterns = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y%m%d",
    ]

    for pattern in patterns:
        try:
            dt = datetime.strptime(date_str, pattern).date()
            return dt
        except ValueError:
            continue

    errors.append(
        f"{field_name} is not a valid date in supported formats "
        f"(expected something like YYYY-MM-DD)"
    )
    return None


def age_in_years(dob: date, today: date) -> int:
    """
    Compute age in completed years.

    Example:
        dob = 2000-12-31, today = 2025-01-01 -> age = 24
    """
    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return years


# ==============================
# Validation logic
# ==============================

def validate_record(
    raw_record: Dict[str, str],
    today: date
) -> Tuple[bool, List[str], Optional[PatientRecord]]:
    """
    Validate a single raw record extracted from the PDF.

    Args:
        raw_record: dictionary containing raw values from PDF.
        today: current date (used for age and 6-month checks).

    Returns:
        (is_valid, errors, normalized_record)
        - is_valid: True/False
        - errors: list of error messages (empty if valid)
        - normalized_record: PatientRecord instance if valid, else None
    """
    errors: List[str] = []

    # Support both "Patient ID" and "PatientID"
    patient_id = (raw_record.get("Patient ID")
                  or raw_record.get("PatientID") or "").strip()
    health_card = (raw_record.get("Health Card Number")
                   or "").replace(" ", "").strip()
    version_code = (raw_record.get("Version Code") or "").strip()
    dob_str = (raw_record.get("Date of Birth") or "").strip()
    service_str = (raw_record.get("Service Date") or "").strip()

    # ---- Rule 1: Health Card Number ----
    if not health_card:
        errors.append("Health card number is missing")
    elif not health_card.isdigit():
        errors.append("Health card number must contain only digits")
    elif len(health_card) != 10:
        errors.append("Health card number must be exactly 10 digits")
    else:
        if not luhn_check(health_card):
            errors.append("Health card number failed MOD 10 (Luhn) validation")

    # ---- Rule 2: Version Code ----
    if not version_code:
        errors.append("Version code is missing")
    elif len(version_code) != 2:
        errors.append("Version code must be exactly 2 characters")
    elif not version_code.isalpha():
        errors.append("Version code must contain only letters A-Z")
    elif not version_code.isupper():
        errors.append("Version code must be uppercase letters (A-Z)")

    # ---- Rule 3: Date of Birth ----
    dob = parse_date_flex(dob_str, "Date of birth", errors)
    if dob:
        # DOB cannot be in the future
        if dob > today:
            errors.append("Date of birth is in the future")
        else:
            age = age_in_years(dob, today)
            if age < 0:
                errors.append("Patient age cannot be negative")
            if age >= 150:
                errors.append("Patient age must be less than 150 years")

    # ---- Rule 4: Service Date ----
    service_date = parse_date_flex(service_str, "Service date", errors)
    if service_date:
        # Service date cannot be in the future
        if service_date > today:
            errors.append("Service date is in the future")

        # Service date cannot be before date of birth
        if dob and service_date < dob:
            errors.append("Service date is before date of birth")

        # Service date cannot be more than 6 months in the past
        # Here we approximate 6 months as 183 days
        six_months_ago = today - timedelta(days=183)
        if service_date < six_months_ago:
            errors.append("Service date is more than 6 months in the past")

    # ---- Basic Patient ID presence check ----
    if not patient_id:
        errors.append("Patient ID is missing")

    # Decide validity
    is_valid = (len(errors) == 0)

    if not is_valid:
        # Return without normalized record
        return False, errors, None

    # Normalize dates into ISO format
    dob_iso = dob.isoformat() if dob else ""
    service_iso = service_date.isoformat() if service_date else ""

    normalized_record = PatientRecord(
        PatientID=patient_id,
        HealthCardNumber=health_card,
        VersionCode=version_code,
        DateOfBirth=dob_iso,
        ServiceDate=service_iso,
    )

    return True, [], normalized_record


# ==============================
# PDF extraction
# ==============================

def extract_records_from_pdf(pdf_path: str) -> List[Dict[str, str]]:
    """
    Extract tabular records from a PDF using pdfplumber.

    Assumptions:
        - PDF contains one or more tables.
        - The first row of each table is a header row.
        - Header columns include something like:
          "Patient ID", "Health Card Number", "Version Code",
          "Date of Birth", "Service Date".

    Returns:
        A list of dictionaries, one per row (record).
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    records: List[Dict[str, str]] = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if not table:
                    continue

                header_row = table[0]
                if not header_row:
                    continue

                # Normalize header strings
                headers: List[str] = []
                for col in header_row:
                    if col is None:
                        headers.append("")
                    else:
                        headers.append(str(col).strip())

                # Iterate over the remaining rows
                for row in table[1:]:
                    if not row:
                        continue
                    # Skip an entirely empty row
                    if all(cell is None or str(cell).strip() == "" for cell in row):
                        continue

                    row_dict: Dict[str, str] = {}
                    for idx, cell in enumerate(row):
                        if idx >= len(headers):
                            continue
                        key = headers[idx]
                        value = "" if cell is None else str(cell).strip()
                        row_dict[key] = value

                    records.append(row_dict)

    except Exception as e:
        raise RuntimeError(f"Error reading or parsing PDF: {e}")

    return records


# ==============================
# Output writers
# ==============================

def write_valid_csv(valid_records: List[PatientRecord], output_path: str) -> None:
    """
    Write valid normalized records to a CSV file.
    """
    fieldnames = ["PatientID", "HealthCardNumber",
                  "VersionCode", "DateOfBirth", "ServiceDate"]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in valid_records:
            writer.writerow(asdict(record))


def write_error_report(
    error_info: List[Tuple[str, List[str]]],
    total_count: int,
    valid_count: int,
    invalid_count: int,
    output_path: str,
) -> None:
    """
    Write a human-readable error report for invalid records.

    Args:
        error_info: list of (PatientID, [error messages])
        total_count: total number of records processed
        valid_count: number of valid records
        invalid_count: number of invalid records
    """
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines: List[str] = []
    lines.append("ERROR REPORT")
    lines.append(f"Generated: {generated_at}")
    lines.append(f"Total Records Processed: {total_count}")
    lines.append(f"Valid Records: {valid_count}")
    lines.append(f"Invalid Records: {invalid_count}")
    lines.append("")
    lines.append("INVALID RECORDS:")

    if invalid_count == 0:
        lines.append("(none)")
    else:
        for patient_id, errors in error_info:
            display_id = patient_id if patient_id else "<MISSING_PATIENT_ID>"
            lines.append(f"Patient ID: {display_id}")
            for err in errors:
                lines.append(f"- {err}")
            lines.append("")  # blank line between records

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ==============================
# Main CLI entry point
# ==============================

def main() -> None:
    """
    Command-line interface entry point.

    Example usage:
        python Health_system.py patient_records_test.pdf
        python Health_system.py patient_records_test.pdf \
            --valid_csv valid_records.csv \
            --error_report error_report.txt
    """
    parser = argparse.ArgumentParser(
        description="Healthcare Claims PDF Extractor & Validator"
    )
    parser.add_argument(
        "pdf_path",
        help="Input PDF file path (e.g., patient_records_test.pdf)"
    )
    parser.add_argument(
        "--valid_csv",
        default="valid_records.csv",
        help="Output CSV file for valid records (default: valid_records.csv)"
    )
    parser.add_argument(
        "--error_report",
        default="error_report.txt",
        help="Output text file for error report (default: error_report.txt)"
    )

    args = parser.parse_args()
    pdf_path = args.pdf_path

    # Extract raw records from PDF
    try:
        raw_records = extract_records_from_pdf(pdf_path)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    if not raw_records:
        print("[WARNING] No records found in PDF.")
        # We still continue and write empty outputs for completeness.

    today = date.today()

    valid_records: List[PatientRecord] = []
    error_info: List[Tuple[str, List[str]]] = []

    # Validate each record
    for raw in raw_records:
        is_valid, errors, normalized = validate_record(raw, today)
        patient_id = (raw.get("Patient ID") or raw.get(
            "PatientID") or "").strip()

        if is_valid and normalized:
            valid_records.append(normalized)
        else:
            error_info.append((patient_id, errors))

    total_count = len(raw_records)
    valid_count = len(valid_records)
    invalid_count = len(error_info)

    # Write outputs
    try:
        write_valid_csv(valid_records, args.valid_csv)
        write_error_report(
            error_info,
            total_count,
            valid_count,
            invalid_count,
            args.error_report,
        )
    except OSError as e:
        print(f"[ERROR] Failed to write output files: {e}", file=sys.stderr)
        sys.exit(1)

    # Console summary
    print("Processing completed.")
