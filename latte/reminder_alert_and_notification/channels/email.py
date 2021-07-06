from latte.reminder_alert_and_notification.channels.abc import ChannelABC,abstractmethod
import frappe
class EmailChannel(ChannelABC):
	def send(self, doc, context):
		from email.utils import formataddr
		subject = self.subject
		if "{" in subject:
			subject = frappe.render_template(self.subject, context)

		attachments = self.get_attachment(doc)
		recipients, cc, bcc = self.get_list_of_recipients(doc, context)
		sender = None
		if self.sender and self.sender_email:
			sender = formataddr((self.sender, self.sender_email))

		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			sender=sender,
			cc=cc,
			bcc=bcc,
			message=frappe.render_template(self.message, context),
			reference_doctype=doc and doc.doctype,
			reference_name=doc and doc.name,
			attachments=attachments,
			print_letterhead=((attachments
			and attachments[0].get('print_letterhead')) or False)
		)
		frappe.db.commit()
