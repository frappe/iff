from collections import defaultdict

import json

import frappe
from frappe.utils import get_url_to_form, getdate, add_months
from frappe.utils.user import get_system_managers
from frappe.integrations.utils import get_payment_gateway_controller, make_post_request
from frappe.contacts.doctype.contact.contact import get_default_contact

from razorpay.constants.url import URL

class EMandatePayment():
	def __init__(self):
		self.successful_transaction = []
		self.failed_transaction = []
		self.plans = get_all_plans()
		self.today = getdate()
		self.next = add_months(getdate(), 1)
		self.enabled = frappe.db.get_single_value("Non Profit Settings", "enable_e_mandate_payments")
		self.controller = get_payment_gateway_controller("Razorpay")
		self.controller.init_client()
		if self.controller.client:
			self.client = self.controller.client
		else:
			frappe.throw("Razorpay Not Setup")

	def trigger_payments(self):
		"""Payment Workflow Utility
			1. Get all members due for payment
			1. Trigger Payment
			1. Update Membership
			1. Log success and failed payments
		"""
		if not self.enabled:
			frappe.throw("Please Enable E Mandate Payments in Non Profit Settings")
		members = self.get_members_due_for_payment()

		if not members:
			return

		for member in members:
			try:
				payment = self.trigger_payment_for_member(member)
				membership = self.update_membership_details(member, payment)
				self.successful_transaction.append(membership)
			except Exception as e:
				title = "E Mandate Payment Error for {0}".format(member.name)
				log = frappe.log_error(e, title)
				self.failed_transaction.append([member.name,get_url_to_form("Error Log", log.name), e])

		send_update_email(self.successful_transaction, self.failed_transaction)

	def get_members_due_for_payment(self):
		"""Compare expiry of all members and return list of members whose payment is due

		Returns:
			list: List of Member docs for whom payment is due
		"""
		all_members = []
		# Get all members for e-mandate processing
		for member_name in frappe.get_all("Member", filters={ "e_mandate": 1, "token_status": "Confirmed" }, as_list=1):
			member = frappe.get_doc("Member", member_name[0])
			expiry = None
			if member.membership_expiry_date:
				expiry = member.membership_expiry_date
			else:
				last_membership = get_last_membership(member.name)
				if last_membership:
					expiry = last_membership["to_date"]

			if (
				member.subscription_end \
				and expiry \
				and expiry <= self.today \
				and self.today < member.subscription_end
			):
				all_members.append(member)

		return all_members


	def trigger_payment_for_member(self, member):
		"""Trigger Razorpay payment and return payment ID

		Args:
			member (object): Member doctype object

		Returns:
			string: Razorpay payment ID
		"""
		# https://razorpay.com/docs/api/recurring-payments/emandate/subsequent-payments/
		amount = self.plans[member.membership_type] * 100 # convert rupee to paise

		order = self.client.order.create(data = {
			"amount": amount,
			"currency": "INR",
			"payment_capture": 1
		})

		order_id = order.get("id")
		if not order_id:
			frappe.throw("Could not create order")

		if not member.contact:
			frappe.throw("Member contact details missing")

		if not member.customer_id:
			frappe.throw("Member customer is missing")

		if not member.razorpay_token:
			frappe.throw("Razorpay token is missing")

		# Razorpay python does not have recurrig payments yet
		# use razorpay client to make requests
		url = "{}/payments/create/recurring".format(URL.BASE_URL)

		data = {
			"email": member.email_id or member.email,
			"contact": member.contact,
			"amount": amount,
			"currency": "INR",
			"order_id": order_id,
			"customer_id": member.customer_id,
			"token": member.get_password(fieldname="razorpay_token"),
			"recurring": 1,
			"notes": {
				"erpnext-name": member.name
			}
		}

		payment = make_post_request(
			url,
			auth=(self.controller.api_key, self.controller.get_password(fieldname="api_secret", raise_exception=False)),
			data=json.dumps(data),
			headers={
				"content-type": "application/json"
			}
		)

		return payment.get("razorpay_payment_id")


	def update_membership_details(self, member, payment):
		membership = frappe.new_doc("Membership")

		# Take date explicitly from members, since
		# payment attempts can fail and be retried the next day
		from_date = member.membership_expiry_date
		to_date = add_months(from_date, 1)

		membership.update({
			"member": member.name,
			"membership_status": "Current",
			"membership_type": member.membership_type,
			"currency": "INR",
			"paid": 1,
			"payment_id": payment,
			"from_date": from_date,
			"to_date": to_date,
			"amount": self.plans[member.membership_type]
		})
		membership.insert(ignore_permissions=True)

		member.membership_expiry_date = to_date
		member.save(ignore_permissions=True)

		settings = frappe.get_doc("Non Profit Settings")
		if settings.allow_invoicing and settings.automate_membership_invoicing:
			membership.generate_invoice(with_payment_entry=settings.automate_membership_payment_entries, save=True)

		return membership

def send_update_email(successful, failed):
	if len(successful) and len(failed):
		frappe.sendmail(
			subject="E Mandate Payments Summary",
			recipients=get_system_managers(),
			template="emandate",
			args={
				"successful": successful,
				"failed": failed
			}
		)

def get_last_membership(member):
	"""Returns last membership if exists"""
	last_membership = frappe.get_all("Membership", "name,to_date,membership_type",
		dict(member=member, paid=1), order_by="to_date desc", limit=1)

	return last_membership and last_membership[0]

def get_all_plans():
	all_plans = {}
	plans = frappe.get_all("Membership Type", fields=["name", "amount"])
	for plan in plans:
		all_plans[plan["name"]] = plan["amount"]

	return all_plans

def execute():
	if not frappe.db.get_single_value("Non Profit Settings", "enable_e_mandate_payments"):
		print("E Mandate Payment is Disabled")
		return
	em = EMandatePayment()
	em.trigger_payments()