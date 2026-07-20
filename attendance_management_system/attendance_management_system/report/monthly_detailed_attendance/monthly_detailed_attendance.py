# Copyright (c) 2026, Pratul Tripathi and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from calendar import monthrange, month_name
from datetime import datetime, timedelta
from frappe.utils import to_timedelta, getdate

def execute(filters=None):
    if not filters: return [], []
    
    try:
        months_list = list(month_name)
        filters.month_num = months_list.index(filters.month)
    except ValueError:
        frappe.throw(_("Invalid Month: {0}").format(filters.month))

    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data

def get_columns(filters):
    columns = [{"label": _("Employee / Metrics"), "fieldname": "metric", "fieldtype": "Data", "width": 250}]
    month_num = filters.month_num
    year = int(filters.year)
    days_in_month = monthrange(year, month_num)[1]

    for day in range(1, days_in_month + 1):
        columns.append({
            "label": _("Day {0}").format(day),
            "fieldname": f"day_{day}",
            "fieldtype": "Data",
            "width": 65
        })
    return columns

def format_timedelta(td):
    if not td: return "00:00"
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"

def round_ot_minutes(hours_float, round_val_mins=30):
    if not hours_float: return 0.0
    total_minutes = hours_float * 60
    rounded_minutes = round(total_minutes / round_val_mins) * round_val_mins
    return rounded_minutes / 60

def get_data(filters):
    month_num = filters.month_num
    year = int(filters.year)
    days_in_month = monthrange(year, month_num)[1]
    start_date_str = f"{year}-{month_num:02d}-01"
    end_date_str = f"{year}-{month_num:02d}-{days_in_month}"
    
    start_date_obj = getdate(start_date_str)
    end_date_obj = getdate(end_date_str)

    # --- 1. Filter Shift Assignments ---
    sa_filters = {
        "company": filters.company,
        "docstatus": 1,
        "status": "Active",
        "start_date": ["<=", end_date_str]
    }
    if filters.get("branch"):
        sa_filters["custom_branch"] = filters.branch

    assignments = frappe.get_all("Shift Assignment", filters=sa_filters, fields=["employee", "shift_type", "start_date", "end_date"])
    if not assignments: return []

    shift_map = {}
    emp_ids = set()
    for assign in assignments:
        s_date = assign.start_date
        e_date = assign.end_date if assign.end_date else end_date_obj
        curr = s_date
        while curr <= e_date:
            if start_date_obj <= curr <= end_date_obj:
                shift_map.setdefault(assign.employee, {})[str(curr)] = assign.shift_type
                emp_ids.add(assign.employee)
            curr += timedelta(days=1)

    if not emp_ids: return []

    # --- 2. Rules Fetching (Late, OT, Attendance) ---
    rule_filters = {"company": filters.company, "start_date": ["<=", end_date_str]}
    if filters.get("branch"): rule_filters["branch"] = filters.branch

    # Attendance Rule
    att_rule_raw = frappe.get_all("Attendance Rule", filters={**rule_filters, "active": 1}, fields=["*"])
    att_rule = next((r for r in att_rule_raw if not r.end_date or r.end_date >= start_date_obj), None)

    # Late Rules Mapping
    late_rules_raw = frappe.get_all("Late Rule", filters={**rule_filters, "is_active": 1}, fields=["*"])
    late_rule_map = {lr.shift_type: lr for lr in late_rules_raw if not lr.end_date or lr.end_date >= start_date_obj}

    # Overtime Rules Mapping
    ot_rules_raw = frappe.get_all("Overtime Rule", filters={**rule_filters, "is_active": 1}, fields=["*"])
    ot_rule_map = {otr.shift_type: otr for otr in ot_rules_raw if not otr.end_date or otr.end_date >= start_date_obj}

    # --- 3. Master Data Fetching ---
    employees = frappe.get_all("Employee", filters={"name": ["in", list(emp_ids)]}, fields=["name", "employee_name", "holiday_list"])
    shift_timing_map = {st.name: {"start": to_timedelta(st.start_time), "end": to_timedelta(st.end_time)} 
                        for st in frappe.get_all("Shift Type", fields=["name", "start_time", "end_time"])}

    checkins = frappe.db.sql(f"""
        SELECT employee, DATE(time) as date, MIN(time) as in_time, MAX(time) as out_time 
        FROM `tabEmployee Checkin` 
        WHERE employee IN %(emp_list)s AND DATE(time) BETWEEN %(start)s AND %(end)s 
        GROUP BY employee, DATE(time)
    """, {"emp_list": list(emp_ids), "start": start_date_str, "end": end_date_str}, as_dict=1)
    checkin_map = {}
    for c in checkins: checkin_map.setdefault(c.employee, {})[str(c.date)] = c

    holiday_map = {}
    for h in frappe.get_all("Holiday", filters={"holiday_date": ["between", [start_date_str, end_date_str]]}, fields=["holiday_date", "parent"]):
        holiday_map.setdefault(h.parent, []).append(str(h.holiday_date))

    # --- 4. Processing ---
    final_data = []
    for emp in employees:
        total_p, total_a, late_count, total_penalty, total_ot_hrs = 0.0, 0, 0, 0.0, 0.0
        total_late_td, total_dur_td = timedelta(), timedelta()

        metric_keys = ["day_name", "shift", "in_time", "out_time", "duration", "late_by", "ot", "status"]
        rows = {m: {"metric": m.replace("_", " ").upper() if m == 'ot' else m.replace("_", " ").title()} for m in metric_keys}
        rows["day_name"]["metric"] = "Day"
        
        emp_holiday_list = emp.holiday_list or frappe.db.get_value("Company", filters.company, "default_holiday_list")
        emp_holidays = holiday_map.get(emp_holiday_list, [])

        for day in range(1, days_in_month + 1):
            date_str = f"{year}-{month_num:02d}-{day:02d}"
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            field = f"day_{day}"
            rows["day_name"][field] = date_obj.strftime("%a")
            assigned_shift = shift_map.get(emp.name, {}).get(date_str)
            rows["shift"][field] = assigned_shift or "-"
            for k in metric_keys[2:]: rows[k][field] = "-"

            if date_obj.weekday() == 6 or date_str in emp_holidays:
                rows["shift"][field] = "WO"; rows["status"][field] = "WO"; continue

            log = checkin_map.get(emp.name, {}).get(date_str)
            current_status = "A"

            if log:
                dur = log.out_time - log.in_time
                dur_hrs = dur.total_seconds() / 3600
                rows["in_time"][field] = log.in_time.strftime("%H:%M")
                rows["out_time"][field] = log.out_time.strftime("%H:%M")
                rows["duration"][field] = str(dur).split('.')[0][:5]
                total_dur_td += dur

                # A. Apply Attendance Rule for Status
                if att_rule:
                    if dur_hrs >= att_rule.minimum_hours_for_present:
                        current_status = "P"; total_p += 1
                    elif dur_hrs >= att_rule.minimum_hours_for_half_day:
                        current_status = "HD"; total_p += 0.5
                    else:
                        current_status = "A"; total_a += 1
                else:
                    current_status = "P"; total_p += 1

                if assigned_shift and assigned_shift in shift_timing_map:
                    s_start = shift_timing_map[assigned_shift]["start"]
                    actual_in = to_timedelta(log.in_time.time())
                    
                    # B. Late Rule
                    lr = late_rule_map.get(assigned_shift)
                    if lr and actual_in > (s_start + timedelta(minutes=lr.late_after_minutes)):
                        late_val = actual_in - s_start
                        rows["late_by"][field] = str(late_val).split('.')[0][:5]
                        total_late_td += late_val
                        late_count += 1
                        if late_count > lr.deduction_starts_after:
                            total_penalty += lr.penalty_value
                            current_status += " (LP)"

                    # C. Overtime Rule
                    otr = ot_rule_map.get(assigned_shift)
                    if otr and dur_hrs > otr.overtime_starts_after_hours:
                        raw_ot = dur_hrs - otr.overtime_starts_after_hours if 'dur_hrs' in locals() else (dur_hrs - otr.overtime_starts_after_hours)
                        rounded_ot = round_ot_minutes(raw_ot, otr.round_off_value_minutes or 30)
                        if rounded_ot >= (otr.minimum_overtime_hours or 0.5):
                            f_ot = min(rounded_ot, otr.maximum_ot_per_day or 4.0)
                            rows["ot"][field] = f"{f_ot:.2f}h"; total_ot_hrs += f_ot
            else:
                total_a += 1

            rows["status"][field] = current_status

        # Summary
        final_data.append({"metric": f"<div style='background-color:#f4f4f4; font-weight:bold; padding:5px;'> {emp.name} : {emp.employee_name} </div>"})
        summary_html = (
            f"<div style='color: #2c3e50; font-weight:bold; font-size: 11px; padding: 2px;'>"
            f"P: {total_p} | A: {total_a} | Penalty: {total_penalty} | OT: {total_ot_hrs:.2f}h | "
            f"Late: {format_timedelta(total_late_td)} | Dur: {format_timedelta(total_dur_td)}</div>"
        )
        final_data.append({"metric": summary_html})
        for key in metric_keys: final_data.append(rows[key])
        final_data.append({})

    return final_data