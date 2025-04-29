import frappe

def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data

def get_columns(filters):
    base_columns = [
        {"fieldname": "doctype_name", "label": "Sales Person", "fieldtype": "Data", "width": 200},
        {"fieldname": "custom_customer", "label": "Customer", "fieldtype": "Data", "width": 200},
        {"fieldname": "custom_customer_address", "label": "Customer Address", "fieldtype": "Data", "width": 300},
        {"fieldname": "custom_customer_type", "label": "Customer Type", "fieldtype": "Data", "width": 150},
        {"fieldname": "custom_item_department", "label": "Item Department", "fieldtype": "Data", "width": 200},
        {"fieldname": "fiscal_year", "label": "Fiscal Year", "fieldtype": "Data", "width": 150},
        {"fieldname": "target_amount", "label": "Total Target", "fieldtype": "Currency", "width": 150},
        {"fieldname": "achievement", "label": "Total Achievement", "fieldtype": "Currency", "width": 150},
    ]

    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]

    if filters and filters.get("month"):
        month = filters["month"].lower()
        return base_columns + [
            {"fieldname": month, "label": f"Target {filters['month']}", "fieldtype": "Currency", "width": 120},
            {"fieldname": f"{month}_pct", "label": f"Target {filters['month']} %", "fieldtype": "Percent", "width": 120},
            {"fieldname": f"achievement_{month}", "label": f"Achievement {filters['month']}", "fieldtype": "Currency", "width": 150},
            {"fieldname": f"achievement_{month}_pct", "label": f"Achievement {filters['month']} %", "fieldtype": "Percent", "width": 150},
        ]
    else:
        target_cols = []
        for m in months:
            ml = m.lower()
            target_cols.extend([
                {"fieldname": ml, "label": f"Target {m}", "fieldtype": "Currency", "width": 120},
                {"fieldname": f"{ml}_pct", "label": f"Target {m} %", "fieldtype": "Percent", "width": 100},
            ])
        achievement_cols = []
        for m in months:
            ml = m.lower()
            achievement_cols.extend([
                {"fieldname": f"achievement_{ml}", "label": f"Achievement {m}", "fieldtype": "Currency", "width": 120},
                {"fieldname": f"achievement_{ml}_pct", "label": f"Achievement {m} %", "fieldtype": "Percent", "width": 120},
            ])
        return base_columns + target_cols + achievement_cols

def get_data(filters):
    conditions = []
    values = {}

    if filters:
        if filters.get("sales_person"):
            conditions.append("sp.name = %(sales_person)s")
            values["sales_person"] = filters["sales_person"]
        if filters.get("customer"):
            conditions.append("td.custom_customer = %(customer)s")
            values["customer"] = filters["customer"]
        if filters.get("customer_address"):
            conditions.append("td.custom_customer_address = %(customer_address)s")
            values["customer_address"] = filters["customer_address"]
        if filters.get("custom_customer_type"):
            conditions.append("td.custom_customer_type = %(custom_customer_type)s")
            values["custom_customer_type"] = filters["custom_customer_type"]
        if filters.get("custom_item_department"):
            conditions.append("td.custom_item_department = %(custom_item_department)s")
            values["custom_item_department"] = filters["custom_item_department"]
        if filters.get("fiscal_year"):
            conditions.append("td.fiscal_year = %(fiscal_year)s")
            values["fiscal_year"] = filters["fiscal_year"]

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT DISTINCT
            sp.name AS doctype_name,
            td.custom_customer AS custom_customer,
            td.custom_customer_address AS custom_customer_address,
            td.custom_customer_type AS custom_customer_type,
            td.custom_item_department AS custom_item_department,
            td.target_amount AS target_amount,
            td.fiscal_year AS fiscal_year
        FROM
            `tabSales Person` sp
        LEFT JOIN
            `tabTarget Detail` td
        ON
            td.parent = sp.name
        {where_clause}
    """

    results = frappe.db.sql(query, values, as_dict=True)

    data = []
    for row in results:
        total_achievement = get_achievement(
            sales_person=row["doctype_name"],
            customer=row["custom_customer"],
            item_department=row["custom_item_department"]
        )
        row["achievement"] = total_achievement

        monthly_targets = get_monthly_distribution(
            sales_person=row["doctype_name"],
            customer=row["custom_customer"],
            item_department=row["custom_item_department"]
        )
        monthly_achievements = get_monthly_achievement(
            sales_person=row["doctype_name"],
            customer=row["custom_customer"],
            item_department=row["custom_item_department"]
        )

        if filters and filters.get("month"):
            month_key = filters.get("month").lower()
            target = monthly_targets.get(month_key, 0.0)
            achievement = monthly_achievements.get(month_key, 0.0)
            row[month_key] = target
            row[f"{month_key}_pct"] = round((target / row["target_amount"]) * 100, 2) if row["target_amount"] else 0.0
            row[f"achievement_{month_key}"] = achievement
            row[f"achievement_{month_key}_pct"] = round((achievement / row["achievement"]) * 100, 2) if row["achievement"] else 0.0
        else:
            for month_key in monthly_targets:
                target = monthly_targets[month_key]
                achievement = monthly_achievements.get(month_key, 0.0)
                row[month_key] = target
                row[f"{month_key}_pct"] = round((target / row["target_amount"]) * 100, 2) if row["target_amount"] else 0.0
                row[f"achievement_{month_key}"] = achievement
                row[f"achievement_{month_key}_pct"] = round((achievement / row["achievement"]) * 100, 2) if row["achievement"] else 0.0

        data.append(row)

    # ✅ Add total row at the end
    if data:
        total_row = {key: 0.0 for key in data[0].keys()}
        for row in data:
            for key, val in row.items():
                if isinstance(val, (int, float)):
                    total_row[key] += round(val, 2) if "pct" in key else val

        total_row["doctype_name"] = "Total ↓"
        data.append(total_row)

    return data

def get_achievement(sales_person, customer, item_department):
    delivery_notes = frappe.db.sql("""
        SELECT DISTINCT dn.name
        FROM `tabDelivery Note` dn
        LEFT JOIN `tabSales Team` st ON st.parent = dn.name
        WHERE dn.customer = %(customer)s
          AND st.sales_person = %(sales_person)s
          AND dn.docstatus = 1
    """, {
        "customer": customer,
        "sales_person": sales_person
    }, as_dict=True)

    achievement_total = 0.0
    for dn in delivery_notes:
        items = frappe.db.sql("""
            SELECT item_code, amount
            FROM `tabDelivery Note Item`
            WHERE parent = %(dn_name)s
        """, {"dn_name": dn.name}, as_dict=True)

        for item in items:
            item_department_match = frappe.db.get_value("Item", item.item_code, "custom_item_department")
            if item_department_match == item_department:
                achievement_total += item.amount or 0.0

    return achievement_total

def get_monthly_distribution(sales_person, customer, item_department):
    monthly = {m: 0.0 for m in [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december"
    ]}

    td = frappe.db.sql("""
        SELECT td.distribution_id, td.target_amount
        FROM `tabTarget Detail` td
        WHERE td.parent = %(sales_person)s
          AND td.custom_customer = %(customer)s
          AND td.custom_item_department = %(item_department)s
        LIMIT 1
    """, {
        "sales_person": sales_person,
        "customer": customer,
        "item_department": item_department
    }, as_dict=True)

    if not td or not td[0].distribution_id:
        return monthly

    distribution_id = td[0].distribution_id
    target_amount = td[0].target_amount or 0.0

    percentages = frappe.db.sql("""
        SELECT month, percentage_allocation
        FROM `tabMonthly Distribution Percentage`
        WHERE parent = %(distribution_id)s
    """, {"distribution_id": distribution_id}, as_dict=True)

    for row in percentages:
        month_key = row["month"].lower()
        percent = row["percentage_allocation"] or 0.0
        if month_key in monthly:
            monthly[month_key] = round((percent / 100.0) * target_amount, 2)

    return monthly

def get_monthly_achievement(sales_person, customer, item_department):
    monthly_achievement = {m: 0.0 for m in [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december"
    ]}

    delivery_notes = frappe.db.sql("""
        SELECT dn.name, dn.posting_date
        FROM `tabDelivery Note` dn
        LEFT JOIN `tabSales Team` st ON st.parent = dn.name
        WHERE dn.customer = %(customer)s
          AND st.sales_person = %(sales_person)s
          AND dn.docstatus = 1
    """, {
        "customer": customer,
        "sales_person": sales_person
    }, as_dict=True)

    for dn in delivery_notes:
        month_key = dn.posting_date.strftime("%B").lower()
        items = frappe.db.sql("""
            SELECT item_code, amount
            FROM `tabDelivery Note Item`
            WHERE parent = %(dn_name)s
        """, {"dn_name": dn.name}, as_dict=True)

        for item in items:
            item_department_match = frappe.db.get_value("Item", item.item_code, "custom_item_department")
            if item_department_match == item_department:
                monthly_achievement[month_key] += item.amount or 0.0

    return monthly_achievement
