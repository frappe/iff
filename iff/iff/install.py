import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def after_install():
	create_e_mandate_custom_fields()
	frappe.db.commit()

def create_e_mandate_custom_fields():
	create_custom_field('Member', {
		'label': _('Payment Via E Mandate?'),
		'fieldname': 'e_mandate',
		'fieldtype': 'Check',
		'insert_after': 'subscription_end'
	})

	create_custom_field('Member', {
		'label': _('PAN Details'),
		'fieldname': 'pan_number',
		'fieldtype': 'Data',
		'insert_after': 'email'
	})

	create_custom_field('Member', {
		'label': _('Razorpay Token'),
		'fieldname': 'razorpay_token',
		'fieldtype': 'Data',
		'insert_after': 'e_mandate'
	})

	create_custom_field('Member', {
		'label': _('Token Status'),
		'fieldname': 'token_status',
		'fieldtype': 'Select',
		'options': '\nInitiated\nConfirmed\nRejected',
		'read_only': 1,
		'insert_after': 'razorpay_token'
	})

