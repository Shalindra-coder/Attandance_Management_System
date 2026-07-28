// Copyright (c) 2026, App Publisher: Shalindra Aporiya and contributors
// For license information, please see license.txt

frappe.ui.form.on("Holiday List Rule", {
    start_date(frm) {
        validate_dates(frm);
    },

    end_date(frm) {
        validate_dates(frm);
    }
});

function validate_dates(frm) {
    if (
        frm.doc.start_date &&
        frm.doc.end_date &&
        frappe.datetime.str_to_obj(frm.doc.start_date) >
        frappe.datetime.str_to_obj(frm.doc.end_date)
    ) {
        frappe.msgprint({
            title: __("Invalid Date"),
            indicator: "red",
            message: __("Start Date cannot be later than End Date.")
        });

        frm.set_value("start_date", "");
    }
}