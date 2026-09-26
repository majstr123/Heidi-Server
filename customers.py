"""
Heidi Server — Project Explorer: Customers & Postal endpoints

Provides REST access to customer_data and postnestevilke tables.
Queries mirror exactly what the Qt client does in:
  - customerdialog.cpp (CRUD, load, list, delete with usage check)
  - newprojectdialog.cpp (suggestions, lookup, title_short)
  - projecteditdialog.cpp (select customer, update title_short)
"""

from __future__ import annotations

import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/customers", tags=["customers"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CustomerRow(BaseModel):
    """Full customer_data row."""
    id: int
    title: Optional[str] = None
    alias: Optional[str] = None
    title_short: Optional[str] = None
    address: Optional[str] = None
    house_number: Optional[str] = None
    city: Optional[str] = None
    country_id: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    post: Optional[str] = None
    social_security_number: Optional[str] = None
    vat_number: Optional[str] = None
    phone: Optional[str] = None
    mail: Optional[str] = None


class CustomerCreate(BaseModel):
    """Body for POST /customers."""
    title: str
    alias: Optional[str] = None
    title_short: Optional[str] = None
    address: Optional[str] = None
    house_number: Optional[str] = None
    city: Optional[str] = None
    country_id: Optional[str] = ""
    country: Optional[str] = ""
    postal_code: Optional[str] = None
    post: Optional[str] = None
    social_security_number: Optional[str] = None
    vat_number: Optional[str] = None
    phone: Optional[str] = None
    mail: Optional[str] = None


class CustomerUpdate(BaseModel):
    """Body for PATCH /customers/{id}."""
    title: Optional[str] = None
    alias: Optional[str] = None
    title_short: Optional[str] = None
    address: Optional[str] = None
    house_number: Optional[str] = None
    city: Optional[str] = None
    country_id: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    post: Optional[str] = None
    social_security_number: Optional[str] = None
    vat_number: Optional[str] = None
    phone: Optional[str] = None
    mail: Optional[str] = None


class CustomerSuggestion(BaseModel):
    """One suggestion for the autocomplete dropdown."""
    suggestion: str


class CustomerLookup(BaseModel):
    """Result of a lookup by title/alias."""
    id: int
    title: Optional[str] = None
    title_short: Optional[str] = None
    alias: Optional[str] = None


class PostalLookup(BaseModel):
    """Postal code ↔ city lookup result."""
    number: Optional[int] = None
    city: Optional[str] = None


# ---------------------------------------------------------------------------
# List all customers
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[CustomerRow])
def list_customers():
    """
    Fetch all customers, ordered by title.
    Mirrors loadCustomers in CustomerListDialog.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, title, alias, title_short, address, house_number, city, "
            "  country_id, country, postal_code, post, social_security_number, "
            "  vat_number, phone, mail "
            "FROM customer_data ORDER BY title"
        )
        columns = [desc[0] for desc in cursor.description]
        rows = [CustomerRow(**dict(zip(columns, r))) for r in cursor.fetchall()]
        cursor.close()
    finally:
        conn.close()

    return rows


# ---------------------------------------------------------------------------
# Customer suggestions (autocomplete)
# ---------------------------------------------------------------------------

@router.get("/suggestions", response_model=list[str])
def get_customer_suggestions():
    """
    Return autocomplete suggestions: "title" or "title (alias)".
    Mirrors customer completions in newprojectdialog.cpp constructor.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT "
            "  IF(alias IS NULL OR alias = '', title, CONCAT(title, ' (', alias, ')')) "
            "  AS suggestion "
            "FROM customer_data"
        )
        suggestions = [row[0] for row in cursor.fetchall()]
        cursor.close()
    finally:
        conn.close()

    return suggestions


# ---------------------------------------------------------------------------
# Customer lookup (by title / alias)
# ---------------------------------------------------------------------------

@router.get("/lookup", response_model=Optional[CustomerLookup])
def lookup_customer(
    title: Optional[str] = Query(None, description="Exact customer title"),
    alias: Optional[str] = Query(None, description="Exact customer alias"),
    input: Optional[str] = Query(None, description="Title OR alias (for fuzzy matching)"),
):
    """
    Look up a customer by title+alias or by a combined input field.
    Mirrors validateInputs / lookupCustomerId in newprojectdialog.cpp.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if title and alias:
            cursor.execute(
                "SELECT id, title, title_short, alias "
                "FROM customer_data WHERE title = %s AND alias = %s LIMIT 1",
                [title, alias],
            )
        elif input:
            cursor.execute(
                "SELECT id, title, title_short, alias "
                "FROM customer_data WHERE title = %s OR alias = %s LIMIT 1",
                [input, input],
            )
        elif title:
            cursor.execute(
                "SELECT id, title, title_short, alias "
                "FROM customer_data WHERE title = %s LIMIT 1",
                [title],
            )
        else:
            return None

        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()

    if row is None:
        return None
    return CustomerLookup(id=row[0], title=row[1], title_short=row[2], alias=row[3])


# ---------------------------------------------------------------------------
# Select customers (for picker dialog in projecteditdialog)
# ---------------------------------------------------------------------------

@router.get("/select", response_model=list[CustomerLookup])
def select_customers():
    """
    Return all customers for the picker dialog.
    Mirrors selectCustomerViaDialog in projecteditdialog.cpp.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, title, IFNULL(alias,''), IFNULL(title_short,'') "
            "FROM customer_data ORDER BY title, alias"
        )
        rows = [
            CustomerLookup(id=r[0], title=r[1], alias=r[2], title_short=r[3])
            for r in cursor.fetchall()
        ]
        cursor.close()
    finally:
        conn.close()

    return rows


# ---------------------------------------------------------------------------
# Get single customer
# ---------------------------------------------------------------------------

@router.get("/{customer_id}", response_model=CustomerRow)
def get_customer(customer_id: int):
    """
    Fetch a single customer by id.
    Mirrors loadCustomerData in customerdialog.cpp.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, title, alias, title_short, address, house_number, city, "
            "  country_id, country, postal_code, post, social_security_number, "
            "  vat_number, phone, mail "
            "FROM customer_data WHERE id = %s",
            [customer_id],
        )
        columns = [desc[0] for desc in cursor.description]
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return CustomerRow(**dict(zip(columns, row)))


# ---------------------------------------------------------------------------
# Create customer (auto-ID = MAX + 1)
# ---------------------------------------------------------------------------

@router.post("/", response_model=CustomerRow, status_code=201)
def create_customer(body: CustomerCreate):
    """
    Insert a new customer.  Auto-assigns id = MAX(id) + 1.
    Mirrors insertCustomer in customerdialog.cpp.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Get next id
        cursor.execute("SELECT MAX(id) FROM customer_data")
        max_row = cursor.fetchone()
        new_id = (max_row[0] or 0) + 1

        cursor.execute(
            "INSERT INTO customer_data "
            "  (id, title, alias, title_short, address, house_number, city, "
            "   country_id, country, postal_code, post, "
            "   social_security_number, vat_number, phone, mail) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [
                new_id, body.title, body.alias, body.title_short,
                body.address, body.house_number, body.city,
                body.country_id, body.country, body.postal_code, body.post,
                body.social_security_number, body.vat_number,
                body.phone, body.mail,
            ],
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()

    return get_customer(new_id)


# ---------------------------------------------------------------------------
# Update customer
# ---------------------------------------------------------------------------

@router.patch("/{customer_id}", response_model=CustomerRow)
def update_customer(customer_id: int, body: CustomerUpdate):
    """
    Update one or more fields on an existing customer.
    Mirrors updateCustomer in customerdialog.cpp.
    """
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields provided")

    set_clause = ", ".join(f"`{c}` = %s" for c in fields)
    values = list(fields.values()) + [customer_id]

    query = f"UPDATE customer_data SET {set_clause} WHERE id = %s"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, values)
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
    finally:
        conn.close()

    if affected == 0:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return get_customer(customer_id)


# ---------------------------------------------------------------------------
# Delete customer (with usage check)
# ---------------------------------------------------------------------------

@router.get("/{customer_id}/usage-count")
def get_customer_usage(customer_id: int):
    """
    Count how many projects reference this customer.
    Used before delete to warn the user.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM projects WHERE customer_id = %s", [customer_id])
        count = cursor.fetchone()[0]
        cursor.close()
    finally:
        conn.close()

    return {"customer_id": customer_id, "project_count": count}


@router.delete("/{customer_id}")
def delete_customer(customer_id: int):
    """
    Delete a customer.  Caller should check usage-count first.
    Mirrors deleteCustomer in customerdialog.cpp.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM customer_data WHERE id = %s", [customer_id])
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
    finally:
        conn.close()

    if affected == 0:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return {"ok": True, "deleted_id": customer_id}





# ---------------------------------------------------------------------------
# Title-short helpers
# ---------------------------------------------------------------------------

@router.get("/lookup/title-short")
def lookup_title_short(
    title: Optional[str] = Query(None),
    alias: Optional[str] = Query(None),
    input: Optional[str] = Query(None, description="Title OR alias"),
):
    """
    Return just the title_short for a customer.
    Mirrors populateTitleShort in newprojectdialog.cpp.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if title and alias:
            cursor.execute(
                "SELECT title_short FROM customer_data WHERE title = %s AND alias = %s",
                [title, alias],
            )
        elif input:
            cursor.execute(
                "SELECT title_short FROM customer_data WHERE title = %s OR alias = %s",
                [input, input],
            )
        else:
            return {"title_short": None}

        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()

    return {"title_short": row[0] if row else None}


@router.patch("/{customer_id}/title-short")
def update_title_short(customer_id: int, title_short: str = Query(...)):
    """
    Update just the title_short for a customer.
    Mirrors updateTitleShort in newprojectdialog/projecteditdialog.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE customer_data SET title_short = %s WHERE id = %s",
            [title_short, customer_id],
        )
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
    finally:
        conn.close()

    if affected == 0:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return {"ok": True, "id": customer_id, "title_short": title_short}


# ---------------------------------------------------------------------------
# Customer alias by id
# ---------------------------------------------------------------------------

@router.get("/{customer_id}/alias")
def get_customer_alias(customer_id: int):
    """
    Return just the alias for a customer.
    Used by onAddNewCustomer in newprojectdialog.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT alias FROM customer_data WHERE id = %s", [customer_id])
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return {"id": customer_id, "alias": row[0]}


# ---------------------------------------------------------------------------
# Postal code lookup (postnestevilke table)
# ---------------------------------------------------------------------------

postal_router = APIRouter(prefix="/postal", tags=["postal"])


@postal_router.get("/by-code", response_model=Optional[PostalLookup])
def lookup_post_by_code(
    code: str = Query(..., description="Postal code to look up"),
):
    """
    Look up city name by postal code.
    Mirrors lookupPostByPostalCode in customerdialog.cpp.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT number, city FROM postnestevilke "
            "WHERE CAST(number AS CHAR) = %s LIMIT 1",
            [code],
        )
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()

    if row is None:
        return None
    return PostalLookup(number=row[0], city=row[1])


@postal_router.get("/by-city", response_model=Optional[PostalLookup])
def lookup_postal_by_city(
    city: str = Query(..., description="City name to look up"),
):
    """
    Look up postal code by city name.
    Mirrors lookupPostalCodeByPost in customerdialog.cpp.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT number, city FROM postnestevilke "
            "WHERE LOWER(TRIM(city)) = LOWER(TRIM(%s)) LIMIT 1",
            [city],
        )
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()

    if row is None:
        return None
    return PostalLookup(number=row[0], city=row[1])
