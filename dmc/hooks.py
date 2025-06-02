app_name = "dmc"
app_title = "Dmc"
app_publisher = "mina"
app_description = "dmc project"
app_email = "mina.m@datasofteg.com"
app_license = "mit"
# required_apps = []

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/dmc/css/dmc.css"
# app_include_js = "/assets/dmc/js/custom_serial_no_batch_selector.js"
app_include_py = ["dmc.api"]

# include js, css files in header of web template
# web_include_css = "/assets/dmc/css/dmc.css"
# web_include_js = "/assets/dmc/js/dmc.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "dmc/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    # "CustomSerialNoBatchSelector" : "public/js/custom_serial_no_batch_selector.js"
    "Sales Order": "public/js/sales_order_edit.js",
    "Proforma Invoice": "public/js/proforma_invoice_edit.js",
    "Sales Invoice": "public/js/sales_invoice_edit.js",
    "Loan": "public/js/loan_edit.js"

}

# doctype_js = {
#     "Stock Reconciliation": "public/js/stock_reconcilition.override.js",
# }
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "dmc/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "dmc.utils.jinja_methods",
# 	"filters": "dmc.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "dmc.install.before_install"
# after_install = "dmc.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "dmc.uninstall.before_uninstall"
# after_uninstall = "dmc.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "dmc.utils.before_app_install"
# after_app_install = "dmc.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "dmc.utils.before_app_uninstall"
# after_app_uninstall = "dmc.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "dmc.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	# "Sales Order": "dmc.remaining.CustomSalesOrder",
#     "Payment Entry":"dmc.payment_entry.CustomPaymentEntry",
#     "Purchase Request": "dmc.purchase_request_validate.CustomPurchaseRequest  ",
# }
override_doctype_class = {
    "Payment Entry": "dmc.payment_entry.CustomPaymentEntry",
    "Material Request": "dmc.material_request.CustomPurchaseRequest",
    "Permission": "dmc.permission_override.CustomPermission",
    "Leave Application": "dmc.leave_application_override.CustomLeaveApplication",
    "Purchase Receipt": "dmc.overrides.purchase_receipt.CustomPurchaseReceipt"
}

# Document Events
# ---------------
# Hook on document methods and events


# doc_events = {
#     "*": {
#         "on_update": "dmc.workflow_logger.log_workflow_action",
#         "on_load": "dmc.workflow_logger.log_workflow_action",
#         "on_submit": "dmc.workflow_logger.log_workflow_action",
#         # 		"on_cancel": "method",
#         # 		"on_trash": "method"
#     }
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"dmc.tasks.all"
# 	],
# 	"daily": [
# 		"dmc.tasks.daily"
# 	],
# 	"hourly": [
# 		"dmc.tasks.hourly"
# 	],
# 	"weekly": [
# 		"dmc.tasks.weekly"
# 	],
# 	"monthly": [
# 		"dmc.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "dmc.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
#     "erpnext.stock.report.stock_ledger.stock_ledger.execute": "dmc.overrides.stock_ledger_override.execute"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "dmc.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["dmc.utils.before_request"]
# after_request = ["dmc.utils.after_request"]

# Job Events
# ----------
# before_job = ["dmc.utils.before_job"]
# after_job = ["dmc.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"dmc.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }
