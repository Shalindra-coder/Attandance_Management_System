# Copyright (c) 2026, App Publisher: Shalindra Aporiya and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe.model.document import Document
from frappe import _


class AttendanceRule(Document):
    def validate(self):
        self.validate_hours()

    def validate_hours(self):
        if (
            self.minimum_hours_for_half_day
            and self.minimum_hours_for_present
            and self.minimum_hours_for_half_day >= self.minimum_hours_for_present
        ):
            frappe.throw(
                _("Minimum Hours for Half Day must be less than Minimum Hours for Present.")
            )

    