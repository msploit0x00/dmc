from num2words import num2words  # type: ignore
import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def get_cost_center_allocation_naming_series(sales_person):
    employee = frappe.db.get_value("Sales Person", sales_person, "employee")
    if not employee:
        return

    department = frappe.db.get_value("Employee", employee, "department")
    if not department:
        return

    payroll_cost_center = frappe.db.get_value(
        "Department", department, "payroll_cost_center")
    if not payroll_cost_center:
        return

    cost_center_allocation = frappe.get_all(
        "Cost Center Allocation",
        filters={"cost_center": payroll_cost_center},
        fields=["name"]
    )

    return cost_center_allocation[0].name if cost_center_allocation else None


@frappe.whitelist()
def get_batch_and_gtin(item_code):
    batch = frappe.get_all(
        "Batch",
        filters={"item": item_code},
        fields=["name", "custom_gtin"],
        limit=1
    )

    if batch:
        return batch[0]
    return None
# @frappe.whitelist()
# def get_batch_info_for_item(item_code):
#     # Get the latest batch for the item
#     batch = frappe.get_all("Batch",
#                            filters={"item": item_code, "disabled": 0},
#                            fields=["name", "custom_gtin"],
#                            order_by="creation desc",
#                            limit=1
#                            )

#     if not batch:
#         return None

#     return {
#         "batch_no": batch[0].name,
#         "custom_gtin": batch[0].custom_gtin
#     }


# @frappe.whitelist(allow_guest=True)
# def number_to_arabic_words(n):
#     units = ["", "واحد", "اثنان", "ثلاثة", "أربعة",
#              "خمسة", "ستة", "سبعة", "ثمانية", "تسعة"]
#     teens = ["عشرة", "أحد عشر", "اثنا عشر", "ثلاثة عشر", "أربعة عشر",
#              "خمسة عشر", "ستة عشر", "سبعة عشر", "ثمانية عشر", "تسعة عشر"]
#     tens = ["", "", "عشرون", "ثلاثون", "أربعون",
#             "خمسون", "ستون", "سبعون", "ثمانون", "تسعون"]
#     hundreds = ["", "مائة", "مئتان", "ثلاثمائة", "أربعمائة",
#                 "خمسمائة", "ستمائة", "سبعمائة", "ثمانمائة", "تسعمائة"]

#     def convert_hundreds(num):
#         h = num // 100
#         t = (num % 100) // 10
#         u = num % 10
#         words = ""
#         if h > 0:
#             words += hundreds[h] + " "
#         if t == 1:
#             words += teens[u] + " "
#         else:
#             if t > 1:
#                 words += tens[t] + " "
#             if u > 0:
#                 if t > 1:
#                     words += "و " + units[u] + " "
#                 else:
#                     words += units[u] + " "
#         return words.strip()

#     if n == 0:
#         return "صفر"

#     parts = []
#     if n >= 1000:
#         thousands = n // 1000
#         parts.append(convert_hundreds(thousands) + " ألف")
#         n = n % 1000

#     if n > 0:
#         parts.append(convert_hundreds(n))

#     return " و ".join(parts)


# @frappe.whitelist(allow_guest=True)
# def amount_to_words_arabic(amount):
#     integer_part = int(amount)
#     fraction_part = int(round((amount - integer_part) * 100))
#     words = num2words(integer_part, lang='ar')
#     if fraction_part > 0:
#         words += " و " + num2words(fraction_part, lang='ar') + " فلس"
#     return words


# def get_context(context):
#     doc = context.get("doc")
#     if doc:
#         context.amount_in_words = amount_to_words_arabic(doc.rounded_total)
#     return context


# my_app/api/money_utils.py


@frappe.whitelist()
def money_to_arabic_words(amount):
    try:
        amount = float(amount)
        return num2words(amount, lang='ar') + " جنيه" " فقط لا غير"
    except Exception as e:
        return f"خطأ في التحويل: {str(e)}"


@frappe.whitelist()
def money_to_arabic_words_with_qirsh(amount):
    try:
        amount = float(amount)
        pounds = int(amount)
        qirsh = round((amount - pounds) * 100)  # استخراج القروش

        words = num2words(pounds, lang='ar') + " جنيه"
        if qirsh > 0:
            words += " و " + num2words(qirsh, lang='ar') + " قرشاً"

        words += " فقط لا غير"
        return words
    except Exception as e:
        return f"خطأ في التحويل: {str(e)}"


# @frappe.whitelist()
# def set_custom_sales_order_type(doc, method):
#     if doc.custom_supply_order:
#         supply_order = frappe.get_doc("Supply order", doc.custom_supply_order)
#         if getattr(supply_order, "custom_supply_order_type", None) == "Partial Supply Order":
#             doc.custom_sales_order_type = "أمر بيع - هيئة الشراء الموحد"


# @frappe.whitelist()
# def get_supply_order_type(supply_order_name):
#     return frappe.db.get_value("Supply order", supply_order_name, "custom_supply_order_type")


# def set_missing_values(source, target):
#     if customer:
#         target.customer = customer.name
#         target.customer_name = customer.customer_name
#     if source.referral_sales_partner:
#         target.sales_partner = source.referral_sales_partner
#         target.commission_rate = frappe.get_value(
#             "Sales Partner", source.referral_sales_partner, "commission_rate"
#         )

#     # Set custom_sales_order_type if custom_sub_number exists
#     if hasattr(source, 'custom_sub_number') and source.custom_sub_number:
#         target.custom_sub_number = source.custom_sub_number
#         target.custom_sales_order_type = 'أمر بيع - هيئة الشراء الموحد'

#     target.flags.ignore_permissions = ignore_permissions
#     target.delivery_date = nowdate()
#     target.run_method("set_missing_values")
#     target.run_method("calculate_taxes_and_totals")
