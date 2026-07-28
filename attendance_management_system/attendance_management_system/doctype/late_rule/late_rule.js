// Copyright (c) 2026, App Publisher: Shalindra Aporiya and contributors
// For license information, please see license.txt

frappe.ui.form.on("Late Rule", {
    grace_time_minutes(frm) {
        validate_grace_time(frm);
    },

    late_after_minutes(frm) {
        validate_grace_time(frm);
    },

    start_date(frm) {
        validate_grace_time(frm);
    },

    end_date(frm) {
        validate_grace_time(frm);
    }
});

function validate_grace_time(frm) {

    // Start Date vs End Date
    if (
        frm.doc.start_date &&
        frm.doc.end_date &&
        frappe.datetime.str_to_obj(frm.doc.start_date) >
        frappe.datetime.str_to_obj(frm.doc.end_date)
    ) {
        frappe.msgprint({
            title: __("Invalid Date"),
            indicator: "red",
            message: __(
                "Start Date cannot be later than End Date."
            )
        });

        frm.set_value("start_date", "");
        return;
    }

    // Grace Time vs Late After
    const grace_time = flt(frm.doc.grace_time_minutes);
    const late_after = flt(frm.doc.late_after_minutes);

    if (grace_time && late_after && grace_time > late_after) {
        frappe.msgprint({
            title: __("Invalid Value"),
            indicator: "red",
            message: __(
                "Grace Time cannot be greater than Late After. Please enter a Grace Time that is less than or equal to the Late After value."
            )
        });

        frm.set_value("grace_time_minutes", "");
    }
}