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

	customer = client.customer.fetch(customer_id=payment.customer_id)

	member = {
		'member_name': customer.get("name") or customer.get("email"),
		'membership_expiry_date': None,
		'contact': payment.contact,
		'email_id': payment.email,
		'customer_id': payment.customer_id,
		'subscription_activated': 1,
		'subscription_start': getdate(),
		'subscription_end': add_months(getdate, 24),
		'e_mandate': 0,
		'razorpay_token': payment.token_id,
 	}

	if payment.notes and type(payment.notes) == dict:
		notes = '\n'.join("{}: {}".format(k, v) for k, v in payment.notes.items())
		member.add_comment("Comment", notes)
	elif payment.notes and type(payment.notes) == str:
		member.add_comment("Comment", payment.notes)


# @frappe.whitelist(allow_guest=True)
# def token_confirmed():
# 	data = frappe.request.get_data(as_text=True)
# 	try:
# 		verify_signature(data)
# 	except Exception as e:
# 		log = frappe.log_error(e, "Webhook Verification Error")
# 		notify_failure(log)
# 		return { 'status': 'Failed', 'reason': e}

# 	if isinstance(data, six.string_types):
# 		data = json.loads(data)
# 	data = frappe._dict(data)

# 	controller = frappe.get_doc("Razorpay Settings")
# 	controller.init_client()
# 	client = controller.client

# 	token = frappe._dict(data.payload.get("token", {}).get("entity", {}))
# 	member = frappe._dict(token=token.id, e_mandate=1)

# 	member = create_member(frappe._dict({
# 		'fullname': payment.email,
# 		'email': payment.email,
# 		'plan_id': get_plan_from_razorpay_id(subscription.plan_id)
# 	}))

# 	member.subscription_id = subscription.id
# 	member.customer_id = payment.customer_id
# 	if subscription.notes and type(subscription.notes) == dict:
# 		notes = '\n'.join("{}: {}".format(k, v) for k, v in subscription.notes.items())
# 		member.add_comment("Comment", notes)
# 	elif subscription.notes and type(subscription.notes) == str:
# 		member.add_comment("Comment", subscription.notes)