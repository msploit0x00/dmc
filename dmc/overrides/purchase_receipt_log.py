@frappe.whitelist()
def compare_pr_with_invoice(purchase_receipt_name):
    pr = frappe.get_doc("Purchase Receipt", purchase_receipt_name)

    if not pr.custom_purchase_invoice_name:
        frappe.throw(
            "No Purchase Invoice linked in custom_purchase_invoice_name.")

    pi = frappe.get_doc("Purchase Invoice", pr.custom_purchase_invoice_name)

    # Build mapping for invoice items
    pi_items_map = {}
    for item in pi.items:
        key = (item.item_code, item.uom)
        pi_items_map[key] = item

    messages = []

    for pr_item in pr.items:
        key = (pr_item.item_code, pr_item.uom)
        pi_item = pi_items_map.get(key)

        if not pi_item:
            messages.append(
                f"Item {pr_item.item_code} ({pr_item.uom}) not found in invoice.")
            continue

        diffs = []

        if pr_item.rate != pi_item.rate:
            diffs.append(f"rate: PR = {pr_item.rate}, PI = {pi_item.rate}")

        if pr_item.base_rate != pi_item.base_rate:
            diffs.append(
                f"base_rate: PR = {pr_item.base_rate}, PI = {pi_item.base_rate}")

        if pr_item.amount != pi_item.amount:
            diffs.append(
                f"amount: PR = {pr_item.amount}, PI = {pi_item.amount}")

        if pr_item.base_amount != pi_item.base_amount:
            diffs.append(
                f"base_amount: PR = {pr_item.base_amount}, PI = {pi_item.base_amount}")

        if diffs:
            messages.append(
                f"❌ Item {pr_item.item_code} ({pr_item.uom}):\n" + "\n".join(diffs))
        else:
            messages.append(
                f"✅ Item {pr_item.item_code} ({pr_item.uom}): All values match.")

    frappe.msgprint("<br><br>".join(messages))
