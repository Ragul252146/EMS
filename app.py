from flask import Flask, render_template, request, redirect, url_for, flash
from ems_logic import *
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "secret123"

init_db()


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


# ---------------- Add ---------------- #
@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        add_employee(
            request.form["name"],
            request.form["age"],
            request.form["department"],
            request.form["designation"],
            request.form["salary"],
            request.form["email"],
            request.form["phone"],
            request.form["status"],
            "",
        )
        flash("Employee added")
        return redirect(url_for("add"))

    return render_template("add_employee.html", departments=get_departments())


# ---------------- Manage ---------------- #
@app.route("/manage")
def manage():
    conn = sqlite3.connect(DB_FILE)
    df = conn.execute("SELECT * FROM employees").fetchall()
    conn.close()
    return render_template("manage_employees.html", employees=df)


@app.route("/delete/<int:id>")
def delete(id):
    delete_employee(id)
    flash("Employee deleted")
    return redirect(url_for("manage"))


# ---------------- Update ---------------- #
@app.route("/update/<int:id>", methods=["GET", "POST"])
def update(id):
    conn = sqlite3.connect(DB_FILE)
    emp = conn.execute("SELECT * FROM employees WHERE id=?", (id,)).fetchone()
    conn.close()

    if request.method == "POST":
        update_employee(
            id,
            request.form["name"],
            request.form["age"],
            request.form["department"],
            request.form["designation"],
            request.form["salary"],
            request.form["email"],
            request.form["phone"],
            request.form["status"],
            "",
        )
        flash("Updated successfully")
        return redirect(url_for("manage"))

    return render_template(
        "update_employee.html", emp=emp, departments=get_departments()
    )


# ---------------- Attendance ---------------- #
@app.route("/attendance", methods=["GET"])
def attendance():
    conn = sqlite3.connect("employees.db")
    c = conn.cursor()
    c.execute("SELECT id, name FROM employees ORDER BY name")
    employees = c.fetchall()
    conn.close()

    emp_id = request.args.get("emp_id")
    year = request.args.get("year")
    month = request.args.get("month")

    records = None
    if year and month:
        query = "SELECT emp_id, att_date, status FROM attendance WHERE 1=1"
        params = []

        if emp_id and emp_id.lower() != "all":
            query += " AND emp_id=?"
            params.append(emp_id)

        # Month filter
        first = f"{year}-{int(month):02d}-01"
        last = f"{year}-{int(month):02d}-31"
        query += " AND att_date BETWEEN ? AND ?"
        params.extend([first, last])

        conn = sqlite3.connect("employees.db")
        c = conn.cursor()
        c.execute(query, params)
        records = c.fetchall()
        conn.close()

    return render_template(
        "attendance.html", employees=employees, records=records, today=date.today()
    )


# ---------- Mark attendance ----------
@app.route("/attendance/mark", methods=["POST"])
def mark_attendance():
    emp_id = request.form["emp_id"]
    status = request.form["status"]
    att_date = request.form["date"]

    conn = sqlite3.connect("employees.db")
    c = conn.cursor()

    if emp_id == "All":
        # bulk mark
        c.execute("SELECT id FROM employees")
        emp_ids = [row[0] for row in c.fetchall()]
        for eid in emp_ids:
            c.execute(
                "INSERT OR REPLACE INTO attendance (emp_id, att_date, status) VALUES (?,?,?)",
                (eid, att_date, status),
            )
    else:
        # mark single
        c.execute(
            "INSERT OR REPLACE INTO attendance (emp_id, att_date, status) VALUES (?,?,?)",
            (emp_id, att_date, status),
        )

    conn.commit()
    conn.close()

    flash("Attendance marked successfully!")

    return redirect(url_for("attendance"))


# ---------------- Leave ---------------- #
@app.route("/leave", methods=["GET", "POST"])
def leave():
    if request.method == "POST":
        apply_leave(
            request.form["emp_id"],
            request.form["start"],
            request.form["end"],
            request.form["reason"],
        )
        flash("Leave applied")

    leaves = get_leaves()
    return render_template("leave.html", leaves=leaves)


@app.route("/leave/approve/<int:id>")
def approve_leave(id):
    update_leave_status(id, "Approved")
    return redirect(url_for("leave"))


@app.route("/leave/reject/<int:id>")
def reject_leave(id):
    update_leave_status(id, "Rejected")
    return redirect(url_for("leave"))


# ---------------- Reports ---------------- #
@app.route("/reports", methods=["GET", "POST"])
def reports():
    data = None
    if request.method == "POST":
        year = int(request.form["year"])
        month = int(request.form["month"])
        data = attendance_percentage_for_month(year, month)

    return render_template("reports.html", data=data)


if __name__ == "__main__":
    app.run(debug=True)
