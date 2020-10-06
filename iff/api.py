import frappe
import razorpay
from frappe.utils import getdate, add_months

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