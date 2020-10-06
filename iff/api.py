import frappe
import razorpay
from frappe.utils import getdate, add_months, add_years

@frappe.whitelist()
def create_member(name, customer_id, token, phone, email, pan, plan):
	member = frappe.new_doc("Member")
	today = getdate()
	member.update({
		"member_name": name,
		"membership_type": plan,
		"pan_number": pan,
		"email_id": email,
		"contact": phone,
		"razorpay_token": token,
		"customer_id": customer_id,
		"subscription_activated": 1,
		"token_status": "Initiated",
		"e_mandate": 1,
		"subscription_start": today,
		"subscription_end": add_years(today, 2),
	})
	member.insert()

def verify_signature(data):
	signature = frappe.request.headers.get('X-Razorpay-Signature')
	key = frappe.get_doc("Membership Settings").get_webhook_secret()
	controller = frappe.get_doc("Razorpay Settings")

	controller.verify_signature(data, signature, key)


@frappe.whitelist(allow_guest=True)
def payment_authorized():
	# https://razorpay.com/docs/api/recurring-payments/webhooks/#payment-authorized
	data = frappe.request.get_data(as_text=True)
	try:
		verify_signature(data)
	except Exception as e:
		log = frappe.log_error(e, "Webhook Verification Error")
		notify_failure(log)
		return { 'status': 'Failed', 'reason': e}

	if isinstance(data, six.string_types):
		data = json.loads(data)
	data = frappe._dict(data)

	payment = data.payload.get("payment", {}).get('entity', {})
	payment = frappe._dict(payment)

	controller = frappe.get_doc("Razorpay Settings")
	controller.init_client()
	client = controller.client

	member = frappe.db.exists('Member', {'customer_id': payment.customer_id})

	if member:
		frappe.db.set_value("Member", member, 'razorpay_token', payment.token_id)
	else:
		customer = client.customer.fetch(customer_id=payment.customer_id)
		frappe.sendmail(
			subject='Could not Capture Authorized Member',
			recipients=get_system_managers(),
			template="capture-failed",
			args={
				'member_name': customer.get("name") or customer.get("email"),
				'membership_expiry_date': None,
				'contact': payment.contact,
				'email_id': payment.email,
				'customer_id': payment.customer_id,
				'subscription_activated': 1,
				'razorpay_token': payment.token_id,
			}
		)

@frappe.whitelist(allow_guest=True)
def token_confirmed():
	# https://razorpay.com/docs/api/recurring-payments/webhooks/#token-confirmed
	data = frappe.request.get_data(as_text=True)
	try:
		verify_signature(data)
	except Exception as e:
		log = frappe.log_error(e, "Webhook Verification Error")
		notify_failure(log)
		return { 'status': 'Failed', 'reason': e}

	if isinstance(data, six.string_types):
		data = json.loads(data)
	data = frappe._dict(data)

	controller = frappe.get_doc("Razorpay Settings")
	controller.init_client()
	client = controller.client

	token = frappe._dict(data.payload.get("token", {}).get("entity", {}))
	member = frappe.db.exists('Member', {'customer_id': payment.customer_id})