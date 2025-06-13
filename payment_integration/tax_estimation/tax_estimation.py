from payment_integration.models import Price


def order_tax_estimation_calculation_payload(customer_ip):
    """
    # Create a tax calculation using Stripe Tax API
    --- IMP: Stripe combines product.tax_code + customer.address to apply the correct local tax rate..

          Mode	        Can Use IP Alone?	                    Recommended
        Test Mode	        ❌ No	                        Use full address
        Live Mode	        ✅ Yes (with fallback)	        Use full address if possible for accuracy
    """
    stripe_product_id = "prod_SB0DJPDZBDa5tJ"
    amount_cents = 1000  # e.g., 1000 cents for $10.00
    customer_ip = customer_ip
    payload = {
        # 1)
        "currency": "usd",  # Currency used for the transaction (must be lowercase ISO code)

        # 2)
        # Customer details are required for tax jurisdiction determination.
        # This tells Stripe: “This customer is in New York, USA.”
        # It answers: “Which government’s tax rules should apply?"
        # (As some items are tax-exempt in some states)
        # (THis details Decides tax Rate with help of getting "tax ID" from below provided customer_details
        # and product.tax_code (product tax code.))

        # (2.1)
        # "customer_details": {
        #     "id": "cust_ABC123",  # Stripe CustomerId
        # },
        # --------------OR--------------------
        # (2.2)
        "customer_details": {
            "address": {
                "line1": "123 Example St",  # Customer street address
                "city": "New York",  # City
                "state": "NY",  # State (required for US-based tax)
                "postal_code": "10001",  # ZIP/postal code
                "country": "US"  # Country code (2-letter ISO)
            },
            # Specifies that the above address is a shipping address
            "address_source": "billing"
        },
        # --------------OR--------------------
        # (2.3)
        # "customer_details": {"ip_address": customer_ip},

        # 3)
        # List of items being purchased
        "line_items": [{
            "amount": amount_cents,  # Amount in **cents**, tax-inclusive (i.e., $14.99)
            "reference": "plan_monthly",  # must be unique per line item in a calculation request.
            "tax_behavior": "inclusive",  # Specifies that taxes are included in this amount

            # Below answers: "Is this item taxable?",
            # "What kind of item is this, and how should it be taxed?"
            # 3.1)
            "product": stripe_product_id,  # gets product.tax_code from saved stripe product
            # -------------------OR--------------------
            # 3.2)
            "tax_code": "txcd_10103001",  # SaaS Product Tax Code. If Not Provided, Stripe will use Stripe Default Tax Code...-> txcd_10000000
        }],
        # Expands line_items in the response for full detail access
        "expand": ["line_items"]
    }

    return payload
