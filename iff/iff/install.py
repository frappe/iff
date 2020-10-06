import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def after_install():
	create_e_mandate_custom_fields()
	frappe.db.commit()

def create_e_mandate_custom_fields():
	create_custom_field('Member', {
		'label': _('E Mandate Details'),
		'fieldname': 'e_mandate_section',
		'fieldtype': 'Section Break',
		'insert_after': 'subscription_end'
	})

	create_custom_field('Member', {
		'label': _('Payment Via E Mandate?'),
		'fieldname': 'e_mandate',
		'fieldtype': 'Check',
		'insert_after': 'e_mandate_section'
	})

	create_custom_field('Member', {
		'label': _('PAN Details'),
		'fieldname': 'pan_number',
		'fieldtype': 'Data',
		'insert_after': 'email'
	})

	create_custom_field('Member', {
		'label': _('Contact Number'),
		'fieldname': 'contact',
		'fieldtype': 'Data',
		'insert_after': 'pan_number'
	})

	create_custom_field('Member', {
		'label': _('Razorpay Token'),
		'fieldname': 'razorpay_token',
		'fieldtype': 'Password',
		'insert_after': 'e_mandate'
	})

	create_custom_field('Member', {
		'label': _('Token Status'),
		'fieldname': 'token_status',
		'fieldtype': 'Select',
		'options': '\nInitiated\nConfirmed\nRejected',
		'insert_after': 'razorpay_token'
	})

	create_custom_field('Membership Settings', {
		'label': _('Enable E Mandate Daily Trigger'),
		'fieldname': 'enable_e_mandate_payments',
		'fieldtype': 'Check',
		'insert_after': 'enable_razorpay'
	})

