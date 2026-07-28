# Copyright (c) 2026, Pratul Tripathi and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from calendar import monthrange, month_name
from datetime import datetime, timedelta
from frappe.utils import to_timedelta, getdate

def execute(filters=None):
    """Main entry point for the report."""
    if not filters: return [], []
    
    # 1. Branch filter is mandatory. Check in Shift Assignment logic.
    if not filters.get("branch"):
        return [], []
    
    try:
        months_list = list(month_name)
        filters.month_num = months_list.index(filters.month)
    except ValueError:
        frappe.throw(_("Invalid Month: {0}").format(filters.month))

    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data

def get_columns(filters):
    """Creates the columns for the report."""
    columns = [{"label": _("Employee / Metrics"), "fieldname": "metric", "fieldtype": "Data", "width": 250}]
    year = int(filters.year)
    month_num = filters.month_num
    days_in_month = monthrange(year, month_num)[1]

    for day in range(1, days_in_month + 1):
        columns.append({"label": _("Day {0}").format(day), "fieldname": f"day_{day}", "fieldtype": "Data", "width": 65})
    return columns

def get_data(filters):
    """Processes data checking Branch and Company in Shift Assignment doctype."""
    year = int(filters.year)
    month_num = filters.month_num
    days_in_month = monthrange(year, month_num)[1]
    
    start_date_str = f"{year}-{month_num:02d}-01"
    end_date_str = f"{year}-{month_num:02d}-{days_in_month}"
    start_date_obj = getdate(start_date_str)
    end_date_obj = getdate(end_date_str)

    # --- STEP 1: FETCH SHIFT ASSIGNMENTS (Checking Branch & Company here) ---
    sa_filters = {
        "company": filters.company,
        "custom_branch": filters.branch, # Checking branch in Shift Assignment
        "docstatus": 1,
        "status": "Active",
        "start_date": ["<=", end_date_str]
    }
    
    assignments = frappe.get_all("Shift Assignment", filters=sa_filters, 
                                 fields=["employee", "shift_type", "start_date", "end_date"])

    if not assignments:
        return []

    # Map assignments and get unique employee list
    shift_map = {}
    employee_ids = set()
    for assign in assignments:
        employee_ids.add(assign.employee)
        curr = assign.start_date
        last = assign.end_date if assign.end_date else end_date_obj
        while curr <= last:
            if start_date_obj <= curr <= end_date_obj:
                shift_map.setdefault(assign.employee, {})[str(curr)] = assign.shift_type
            curr += timedelta(days=1)

    # --- STEP 2: FETCH EMPLOYEE MASTER DATA ---
    employees = frappe.get_all("Employee", filters={"name": ["in", list(employee_ids)]}, 
                               fields=["name", "employee_name", "holiday_list", "branch"])

    # --- STEP 3: FETCH RULES ---
    attendance_rules = frappe.get_all("Attendance Rule", filters={"company": filters.company, "active": 1, "branch": filters.branch}, fields=["*"])
    ot_rules = frappe.get_all("Overtime Rule", filters={"company": filters.company, "is_active": 1, "branch": filters.branch}, fields=["*"])
    late_rules = frappe.get_all("Late Rule", filters={"company": filters.company, "is_active": 1, "branch": filters.branch}, fields=["*"])
    holiday_rules = frappe.get_all("Holiday List Rule", filters={"company_name": filters.company, "active": 1, "branch": filters.branch}, fields=["*"])

    # --- STEP 4: FETCH RAW CHECK-IN LOGS (For Night Shift) ---
    next_day_str = (getdate(end_date_str) + timedelta(days=1)).strftime("%Y-%m-%d")
    raw_logs = frappe.get_all("Employee Checkin", 
        filters={"employee": ["in", list(employee_ids)], "time": ["between", [start_date_str + " 00:00:00", next_day_str + " 23:59:59"]]},
        fields=["employee", "time", "log_type"], order_by="time asc")

    logs_by_emp = {}
    for log in raw_logs:
        logs_by_emp.setdefault(log.employee, []).append(log)

    shift_timings = {st.name: {"start": to_timedelta(st.start_time), "end": to_timedelta(st.end_time)} 
                     for st in frappe.get_all("Shift Type", fields=["name", "start_time", "end_time"])}

    # --- STEP 5: PROCESS DAILY DATA ---
    final_data = []
    default_holiday_list = frappe.db.get_value("Company", filters.company, "default_holiday_list")

    for emp in employees:
        total_p, total_a, total_penalty, total_ot_hrs = 0.0, 0, 0.0, 0.0
        metric_keys = ["day_name", "shift", "in_time", "out_time", "duration", "late_by", "ot", "status"]
        rows = {m: {"metric": m.replace("_", " ").title()} for m in metric_keys}
        rows["ot"]["metric"] = "OT"; rows["day_name"]["metric"] = "Day"

        for day_idx in range(1, days_in_month + 1):
            date_str = f"{year}-{month_num:02d}-{day_idx:02d}"
            curr_date = getdate(date_str)
            field = f"day_{day_idx}"
            
            rows["day_name"][field] = curr_date.strftime("%a")
            assigned_shift = shift_map.get(emp.name, {}).get(date_str)
            rows["shift"][field] = assigned_shift or "-"
            for k in metric_keys[2:]: rows[k][field] = "-"

            def find_rule(rule_list, branch, shift, date):
                for r in rule_list:
                    if r.branch and r.branch != branch: continue
                    if r.shift_type and r.shift_type != shift: continue
                    if getdate(r.start_date) > date: continue
                    if r.end_date and getdate(r.end_date) < date: continue
                    return r
                return None

            # Holiday Check
            h_rule = find_rule(holiday_rules, filters.branch, assigned_shift, curr_date)
            active_hl = h_rule.holiday_list if h_rule else (emp.holiday_list or default_holiday_list)
            is_holiday = frappe.db.exists("Holiday", {"parent": active_hl, "holiday_date": date_str})
            
            if curr_date.weekday() == 6 or is_holiday:
                label = "WO" if curr_date.weekday() == 6 else "HL"
                rows["shift"][field] = label; rows["status"][field] = label
                continue

            # Night Shift Pairing Logic
            in_log, out_log = None, None
            emp_logs = logs_by_emp.get(emp.name, [])
            for log in emp_logs:
                if log.time.date() == curr_date:
                    if not in_log or log.time < in_log.time: in_log = log
            
            if in_log:
                limit = in_log.time + timedelta(hours=16)
                for log in emp_logs:
                    if log.time > in_log.time and log.time <= limit:
                        if not out_log or log.time > out_log.time: out_log = log

            # Calculate and apply rules
            if in_log and out_log and in_log != out_log:
                duration = out_log.time - in_log.time
                work_hours = duration.total_seconds() / 3600
                rows["in_time"][field] = in_log.time.strftime("%H:%M")
                rows["out_time"][field] = out_log.time.strftime("%H:%M")
                rows["duration"][field] = str(duration).split('.')[0][:5]

                # Attendance
                att_rule = find_rule(attendance_rules, filters.branch, assigned_shift, curr_date)
                if att_rule:
                    if work_hours >= att_rule.minimum_hours_for_present:
                        rows["status"][field] = "P"; total_p += 1
                    elif work_hours >= att_rule.minimum_hours_for_half_day:
                        rows["status"][field] = "HD"; total_p += 0.5
                    else:
                        rows["status"][field] = "A"; total_a += 1
                else:
                    rows["status"][field] = "P"; total_p += 1

                # Late
                late_rule = find_rule(late_rules, filters.branch, assigned_shift, curr_date)
                if late_rule and assigned_shift in shift_timings:
                    s_start = shift_timings[assigned_shift]["start"]
                    act_in = to_timedelta(in_log.time.time())
                    if act_in > (s_start + timedelta(minutes=late_rule.late_after_minutes)):
                        rows["late_by"][field] = str(act_in - s_start).split('.')[0][:5]
                        total_penalty += late_rule.penalty_value
                        rows["status"][field] += " (LP)"

                # OT
                ot_rule = find_rule(ot_rules, filters.branch, assigned_shift, curr_date)
                if ot_rule and work_hours > ot_rule.overtime_starts_after_hours:
                    raw_ot = work_hours - ot_rule.overtime_starts_after_hours
                    step = (ot_rule.round_off_value_minutes or 30) / 60
                    rounded_ot = round(raw_ot / step) * step
                    if rounded_ot >= (ot_rule.minimum_overtime_hours or 0.5):
                        act_ot = min(rounded_ot, ot_rule.maximum_ot_per_day or 4.0)
                        rows["ot"][field] = f"{act_ot:.2f}h"; total_ot_hrs += act_ot
            else:
                rows["status"][field] = "A"; total_a += 1

        final_data.append({"metric": f"<div style='background-color:#f4f4f4; font-weight:bold; padding:5px;'> {emp.name} : {emp.employee_name} </div>"})
        summary = f"<b>P:</b> {total_p} | <b>A:</b> {total_a} | <b>Penalty:</b> {total_penalty} | <b>OT:</b> {total_ot_hrs:.2f}h"
        final_data.append({"metric": f"<div style='padding: 2px; font-size: 11px;'>{summary}</div>"})
        for key in metric_keys: final_data.append(rows[key])
        final_data.append({})

    return final_data