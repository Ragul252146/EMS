import sqlite3
import os
import re
import sys
import shutil
import pandas as pd
import qrcode
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import date, datetime
import calendar

DB_FILE = "employees.db"
QR_FOLDER = "static/qr_codes"
os.makedirs(QR_FOLDER, exist_ok=True)

# ---------------- Database Setup ---------------- #
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER,
            department TEXT,
            designation TEXT,
            salary REAL,
            email TEXT,
            phone TEXT,
            status TEXT DEFAULT 'Active',
            photo TEXT DEFAULT ''
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id INTEGER NOT NULL,
            att_date TEXT NOT NULL,
            status TEXT NOT NULL,
            UNIQUE(emp_id, att_date)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'Applied',
            applied_on TEXT
        )
    ''')
    for dept in ['HR', 'IT', 'Sales', 'Finance']:
        c.execute("INSERT OR IGNORE INTO departments (name) VALUES (?)", (dept,))
    conn.commit()
    conn.close()

# ---------------- Utility Functions ---------------- #
def get_departments():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT name FROM departments")
    d = [row[0] for row in c.fetchall()]
    conn.close()
    return d

def generate_qr(emp):
    emp_id, name, _, department, designation = emp[0], emp[1], '', emp[3], emp[4]
    qr_data = f"ID: {emp_id}\nName: {name}\nDept: {department}\nDesig: {designation}"
    qr_img = qrcode.make(qr_data)
    path = f"{QR_FOLDER}/{emp_id}_{name}.png"
    qr_img.save(path)
    return path

def generate_qr_for_id(emp_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM employees WHERE id=?", (emp_id,))
    emp = c.fetchone()
    conn.close()
    if emp:
        return generate_qr(emp)

# ---------------- CRUD ---------------- #
def add_employee(name, age, dept, desig, salary, email, phone, status, photo):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''INSERT INTO employees (name, age, department, designation, salary, email, phone, status, photo)
              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (name, age, dept, desig, salary, email, phone, status, photo))
    conn.commit()
    emp_id = c.lastrowid
    conn.close()
    generate_qr_for_id(emp_id)

def update_employee(emp_id, name, age, dept, desig, salary, email, phone, status, photo):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''UPDATE employees
                 SET name=?, age=?, department=?, designation=?, salary=?, email=?, phone=?, status=?, photo=?
                 WHERE id=?''',
              (name, age, dept, desig, salary, email, phone, status, photo, emp_id))
    conn.commit()
    conn.close()
    generate_qr_for_id(emp_id)

def delete_employee(emp_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM employees WHERE id=?", (emp_id,))
    conn.commit()
    conn.close()

# ---------------- Attendance ---------------- #
def get_attendance(emp_id=None, year=None, month=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    query = "SELECT emp_id, att_date, status FROM attendance WHERE 1=1"
    params = []

    if emp_id and emp_id != "All":
        query += " AND emp_id=?"
        params.append(emp_id)

    if year and month:
        first = date(year, month, 1).isoformat()
        last = date(year, month, calendar.monthrange(year, month)[1]).isoformat()
        query += " AND att_date BETWEEN ? AND ?"
        params.extend([first, last])

    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return rows

def attendance_percentage_for_month(year, month):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    first = date(year, month, 1).isoformat()
    last = date(year, month, calendar.monthrange(year, month)[1]).isoformat()

    c.execute('''
        SELECT e.id, e.name,
               SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END),
               COUNT(a.id)
        FROM employees e
        LEFT JOIN attendance a ON e.id = a.emp_id AND a.att_date BETWEEN ? AND ?
        GROUP BY e.id, e.name
    ''', (first, last))

    rows = c.fetchall()
    conn.close()

    result = []
    for emp_id, name, present, total in rows:
        pct = (present / total * 100) if total else 0
        result.append((emp_id, name, present or 0, total or 0, round(pct, 2)))

    return result

# ---------------- Leaves ---------------- #
def apply_leave(emp_id, start, end, reason):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''INSERT INTO leaves (emp_id, start_date, end_date, reason, applied_on)
                 VALUES (?, ?, ?, ?, ?)''',
              (emp_id, start, end, reason, date.today().isoformat()))
    conn.commit()
    conn.close()

def update_leave_status(leave_id, status):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE leaves SET status=? WHERE id=?", (status, leave_id))
    conn.commit()
    conn.close()

def get_leaves():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM leaves", conn)
    conn.close()
    return df.values.tolist()

# ---------------- Export ---------------- #
def export_attendance_to_csv(emp_id, year, month, out):
    df = pd.DataFrame(get_attendance(emp_id, year, month),
                      columns=["emp_id", "date", "status"])
    df.to_csv(out, index=False)

def export_attendance_to_excel(emp_id, year, month, out):
    df = pd.DataFrame(get_attendance(emp_id, year, month),
                      columns=["emp_id", "date", "status"])
    df.to_excel(out, index=False)

def generate_payslip_pdf(emp_id, year, month, out):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, name, designation, department, salary FROM employees WHERE id=?", (emp_id,))
    emp = c.fetchone()
    conn.close()

    rows = get_attendance(emp_id, year, month)
    present = sum(1 for r in rows if r[2] == "Present")
    total = calendar.monthrange(year, month)[1]

    pay = emp[4] * (present / total) if total else 0

    pdf = canvas.Canvas(out, pagesize=letter)
    pdf.drawString(50, 750, f"Payslip for {emp[1]}")
    pdf.drawString(50, 720, f"Present Days: {present}/{total}")
    pdf.drawString(50, 700, f"Payable Salary: {round(pay,2)}")
    pdf.save()
