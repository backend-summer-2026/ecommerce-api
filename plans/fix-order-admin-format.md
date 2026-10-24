# Bugfix Plan: OrderAdmin total_price_display SafeString formatting error

## Metadata
- **Title**: Fix ValueError in OrderAdmin total_price_display method
- **Date**: 2026-10-24
- **Status**: COMPLETED
- **Branch**: `fix/order-admin-format-error`
- **Author**: Antigravity

---

## 1. Problem Description

When navigating to `/admin/orders/order/`, Django raises:
```
ValueError: Unknown format code 'f' for object of type 'SafeString'
```
Location: `apps/orders/admin.py` line 195 in `total_price_display`:
```python
return format_html(
    '<strong>{:,.2f} {}</strong>',
    obj.total_price,
    obj.currency,
)
```
`format_html` applies `conditional_escape` to its arguments before string interpolation, turning `obj.total_price` (Decimal) into a `SafeString`. Python does not allow numeric format specifiers like `{:,.2f}` on string objects, resulting in a `ValueError`.

---

## 2. Solution Design

Format the Decimal before passing it into `format_html`:
```python
return format_html(
    '<strong>{} {}</strong>',
    f"{obj.total_price:,.2f}",
    obj.currency,
)
```

---

## 3. Checklist
- [x] Step 1: Create dedicated branch `fix/order-admin-format-error`
- [x] Step 2: Fix `total_price_display` method in `apps/orders/admin.py`
- [x] Step 3: Verify fix by testing `OrderAdmin.total_price_display` and admin changelist request
- [x] Step 4: Run test suite (`python manage.py test apps.orders`)
- [x] Step 5: Merge branch into `dev` and delete `fix/order-admin-format-error`
