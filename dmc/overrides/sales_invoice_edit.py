# your_app/sales_invoice_hooks.py
import frappe


def set_series_from_sales_order(doc, method):
    """
    قبل إدخال Sales Invoice، فرض naming_series/series اعتمادًا على Sales Order.custom_sales_order_type
    (نضبط كلاً من naming_series و series لضمان التوافق مع أي نسخة من Frappe).
    """
    try:
        # فقط إذا هناك Sales Order مرتبط
        if not getattr(doc, "sales_order", None):
            return

        # إذا الـ series أو naming_series بالفعل معبئتين وتريد عدم الاستبدال، ازل التعليق عن السطور التالية:
        # if (getattr(doc, "naming_series", None) or getattr(doc, "series", None)):
        #     return

        so = frappe.get_doc("Sales Order", doc.sales_order)
        so_type = (so.get("custom_sales_order_type") or "").strip()
        frappe.log("Sales Invoice hook: Sales Order {0} type: {1}".format(
            doc.sales_order, so_type))

        # خريطة بين نوع أمر البيع و naming series المرغوب
        mapping = {
            "أمر بيع -بيان": "INV-PRF-",   # عدّل إلى الاسم الموجود عندك في Naming Series
            "أمر بيع نقدى": "ACC-SINV-RET-YYYY-",
            # أضف المزيد هنا إذا لزم
        }

        target_series = mapping.get(so_type)
        if target_series:
            # ضمّن الحقلين لأن بعض الإصدارات تستخدم واحد بدل الآخر
            doc.naming_series = target_series
            doc.series = target_series
            # أيضا لو هناك حقل 'naming_series' في meta مختلف، لا بأس، نترك القيمة هنا
            frappe.log(
                "Sales Invoice hook: set naming_series/series to {0}".format(target_series))

    except Exception as e:
        # لا تفشل العملية بسبب خطأ هنا — سجّل الخطأ لفحصه
        frappe.log_error(frappe.get_traceback(), "set_series_from_sales_order")
