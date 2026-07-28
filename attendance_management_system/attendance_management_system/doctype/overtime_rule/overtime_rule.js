// Copyright (c) 2026, App Publisher: Shalindra Aporiya and contributors
// For license information, please see license.txt

frappe.ui.form.on("Overtime Rule", {
    minimum_overtime(frm) {
        validate_overtime(frm);
    },

    maximum_overtime(frm) {
        validate_overtime(frm);
    },

    maximum_ot_per_day(frm) {
        validate_overtime(frm);
    },

    maximum_ot_per_month(frm) {
        validate_overtime(frm);
    },

    start_date(frm) {
        validate_overtime(frm);
    },

    end_date(frm) {
        validate_overtime(frm);
    },

    validate(frm) {
        validate_overtime(frm);
    }
});

function validate_overtime(frm) {

    // Start Date vs End Date
    if (
        frm.doc.start_date &&
        frm.doc.end_date &&
        frappe.datetime.str_to_obj(frm.doc.start_date) >
        frappe.datetime.str_to_obj(frm.doc.end_date)
    ) {
        frappe.throw(
            __("Start Date cannot be later than End Date.")
        );
    }

    // Minimum vs Maximum Overtime
    if (
        frm.doc.minimum_overtime_hours &&
        frm.doc.maximum_overtime_hours &&
        flt(frm.doc.minimum_overtime_hours) > flt(frm.doc.maximum_overtime_hours)
    ) {
        frappe.throw(
            __("Minimum Overtime cannot be greater than Maximum Overtime. Please enter a Minimum Overtime that is less than or equal to the Maximum Overtime.")
        );
    }

    // Maximum OT Per Day vs Maximum OT Per Month
    if (
        frm.doc.maximum_ot_per_day &&
        frm.doc.maximum_ot_per_month &&
        flt(frm.doc.maximum_ot_per_day) > flt(frm.doc.maximum_ot_per_month)
    ) {
        frappe.throw(
            __("Maximum OT Per Day cannot be greater than Maximum OT Per Month. Please enter a daily limit that is less than or equal to the Maximum OT Per Month.")
        );
    }
}