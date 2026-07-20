// Copyright (c) 2026, Pratul Tripathi and contributors
// For license information, please see license.txt

frappe.query_reports["Monthly Detailed Attendance"] = {
	"filters": [
				{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("company"),
			"reqd": 1
		},
				{
			"fieldname": "month",
			"label": __("Month"),
			"fieldtype": "Select",
			"options": [
				{ "value": "January", "label": __("January") },
				{ "value": "February", "label": __("February") },
				{ "value": "March", "label": __("March") },
				{ "value": "April", "label": __("April") },
				{ "value": "May", "label": __("May") },
				{ "value": "June", "label": __("June") },
				{ "value": "July", "label": __("July") },
				{ "value": "August", "label": __("August") },
				{ "value": "September", "label": __("September") },
				{ "value": "October", "label": __("October") },
				{ "value": "November", "label": __("November") },
				{ "value": "December", "label": __("December") }
			],
			"default": moment().format("MMMM"), 
			"reqd": 1
		},

		{
			"fieldname": "year",
			"label": __("Year"),
			"fieldtype": "Select",
			"options": "2023\n2024\n2025\n2026",
			"default": frappe.datetime.get_today().split("-")[0],
			"reqd": 1
		},
		// {
		// 	"fieldname": "department",
		// 	"label": __("Department"),
		// 	"fieldtype": "Link",
		// 	"options": "Department"
		// },
		{
			"fieldname": "branch",
			"label": __("Branch"),
			"fieldtype": "Link",
			"options": "Branch"
		},

	],
};
