import frappe
import razorpay
import six
import json
from frappe.integrations.utils import get_payment_gateway_controller, make_post_request
from frappe.utils import getdate, add_months, add_years

def get_client():
	controller = get_payment_gateway_controller("Razorpay")
	controller.init_client()
	return controller.client

@frappe.whitelist()
def create_member(customer_id, plan, pan=None):
	client = get_client()
	customer = frappe._dict(client.customer.fetch(customer_id))

	# defaults
	today = getdate()
	plan = frappe.db.exists("Membership Type", { "razorpay_plan_id": plan })

	member = frappe.new_doc("Member")
	member.update({
		"member_name": customer.name,
		"membership_type": plan,
		"pan_number": pan,
		"email_id": customer.email,
		"contact": customer.contact,
		"customer_id": customer_id,
		"subscription_activated": 1,
		"token_status": "Initiated",
		"subscription_start": today,
		"subscription_end": add_years(today, 2),
	})
	member.insert(ignore_permissions=True)

	return member.name

def verify_signature(data):
	signature = frappe.request.headers.get("X-Razorpay-Signature")
	settings = frappe.get_doc("Non Profit Settings")
	key = settings.get_webhook_secret()
	controller = frappe.get_doc("Razorpay Settings")

	controller.verify_signature(data, signature, key)
	frappe.set_user(settings.creation_user)

@frappe.whitelist(allow_guest=True)
def payment_authorized():
	# https://razorpay.com/docs/api/recurring-payments/webhooks/#payment-authorized
	data = frappe.request.get_data(as_text=True)
	try:
		verify_signature(data)
	except Exception as e:
		log = frappe.log_error(e, "Webhook Verification Error")
		return { "status": "Failed", "reason": e}

	if isinstance(data, six.string_types):
		data = json.loads(data)
	data = frappe._dict(data)

	payment = data.payload.get("payment", {}).get("entity", {})
	payment = frappe._dict(payment)

	controller = frappe.get_doc("Razorpay Settings")
	controller.init_client()
	client = controller.client

	member = frappe.db.exists("Member", {"customer_id": payment.customer_id})
	token_data = client.token.fetch(payment.customer_id, payment.token_id)

	if not member:
		max_amount = token_data.get("max_amount") / 100
		plan = frappe.db.exists("Membership Type", { "amount":  max_amount})
		if plan:
			plan_id = frappe.db.get_value("Membership Type", plan, "razorpay_plan_id")
			member = create_member(payment.customer_id, plan_id)

	if member:
		frappe.db.set_value("Member", member, "razorpay_token", payment.token_id)
		status = token_data.get("recurring_details").get("status")
		if status == "confirmed":
			frappe.db.set_value("Member", member, "token_status", "Confirmed")
		if status == "rejected":
			frappe.db.set_value("Member", member, "token_status", "Rejected")
		return member

@frappe.whitelist(allow_guest=True)
def token_update():
	# https://razorpay.com/docs/api/recurring-payments/webhooks/#token-confirmed
	data = frappe.request.get_data(as_text=True)
	try:
		verify_signature(data)
	except Exception as e:
		log = frappe.log_error(e, "Webhook Verification Error")
		return { "status": "Failed", "reason": e}

	if isinstance(data, six.string_types):
		data = json.loads(data)
	data = frappe._dict(data)

	controller = frappe.get_doc("Razorpay Settings")
	controller.init_client()
	client = controller.client

	token = frappe._dict(data.payload.get("token", {}).get("entity", {}))
	member = frappe.db.exists("Member", {"razorpay_token": token.id})
	if member:
		token_status = "Initiated"
		if data.event in ["token.confirmed", "token.resumed"]:
			token_status = "Confirmed"
		if data.event == "token.rejected":
			token_status = "Rejected"
		if data.event == "token.cancelled":
			token_status = "Cancelled"

		frappe.db.set_value("Member", member, "token_status", token_status)
		return member

@frappe.whitelist(allow_guest=True)
def invoice_paid():
	# https://razorpay.com/docs/api/recurring-payments/webhooks/
	data = frappe.request.get_data(as_text=True)
	try:
		verify_signature(data)
	except Exception as e:
		log = frappe.log_error(e, "Webhook Verification Error")
		return { "status": "Failed", "reason": e}

	if isinstance(data, six.string_types):
		data = json.loads(data)
	data = frappe._dict(data)

	payment = frappe._dict(data.payload.get("payment", {}).get("entity", {}))

	if not payment.method == "emandate":
		return

	controller = frappe.get_doc("Razorpay Settings")
	controller.init_client()
	client = controller.client

	today = getdate()

	member = frappe.db.exists("Member", {"customer_id": payment.customer_id})
	token_data = client.token.fetch(payment.customer_id, payment.token_id)

	if not member:
		max_amount = token_data.get("max_amount") / 100
		plan = frappe.db.exists("Membership Type", { "amount":  max_amount})
		if plan:
			plan_id = frappe.db.get_value("Membership Type", plan, "razorpay_plan_id")
			member = create_member(payment.customer_id, plan_id)

	if member:
		member = frappe.get_doc("Member", member)

		membership = frappe.new_doc("Membership")
		membership.update({
			"member": member.name,
			"membership_status": "New",
			"membership_type": member.membership_type,
			"currency": "INR",
			"paid": 1,
			"payment_id": payment.id,
			"from_date": today,
			"to_date": add_months(today, 1),
			"amount": frappe.db.get_value("Membership Type", member.membership_type, "amount")
		})
		membership.insert(ignore_permissions=True)

		# Update membership values
		member.subscription_activated = 1
		member.e_mandate = 1
		member.razorpay_token = payment.token_id
		status = token_data.get("recurring_details").get("status")
		if status == "confirmed":
			member.token_status = "Confirmed"
		if status == "rejected":
			member.token_status = "Rejected"

		member.membership_expiry_date = add_months(today, 1)
		member.save(ignore_permissions=True)

		settings = frappe.get_doc("Non Profit Settings")
		if settings.allow_invoicing and settings.automate_membership_invoicing:
			membership.generate_invoice(with_payment_entry=settings.automate_membership_payment_entries, save=True)

@frappe.whitelist(allow_guest=True)
def ping():
	return "pong"
