import frappe
from latte.utils.file_patcher import patch
from frappe.utils import cint
import frappe.email.smtp
from frappe.email.smtp import (
	get_outgoing_email_account,
	smtplib,
	raise_,
	_socket,
	sys
)

class PatchedSMTPServer(object):
	def __init__(self, login=None, password=None, server=None, port=None, use_tls=None, append_to=None):
		# get defaults from mail settings

		self._sess = None
		self.email_account = None
		self.server = None
		if server:
			self.server = server
			self.port = port
			self.use_tls = cint(use_tls)
			self.login = login
			self.password = password

		else:
			self.setup_email_account(append_to)

	def setup_email_account(self, append_to=None, sender=None):
		self.email_account = get_outgoing_email_account(raise_exception_not_set=False, append_to=append_to, sender=sender)
		if self.email_account:
			self.server = self.email_account.smtp_server
			self.login = (getattr(self.email_account, "login_id", None) or self.email_account.email_id)
			if not self.email_account.no_smtp_authentication:
				if self.email_account.ascii_encode_password:
					self.password = frappe.safe_encode(self.email_account.password, 'ascii')
				else:
					self.password = self.email_account.password
			else:
				self.password = None
			self.port = self.email_account.smtp_port
			self.use_tls = self.email_account.use_tls
			self.sender = self.email_account.email_id
			self.always_use_account_email_id_as_sender = cint(self.email_account.get("always_use_account_email_id_as_sender"))
			self.always_use_account_name_as_sender_name = cint(self.email_account.get("always_use_account_name_as_sender_name"))

	@property
	def sess(self):
		"""get session"""
		if self._sess:
			return self._sess

		# check if email server specified
		if not getattr(self, 'server'):
			err_msg = 'Email Account not setup. Please create a new Email Account from Setup > Email > Email Account'
			frappe.msgprint(err_msg)
			raise frappe.OutgoingEmailError(err_msg)

		try:
			if self.use_tls and not self.port:
				self.port = 587

			self._sess = smtplib.SMTP((self.server or ""),
				cint(self.port) or None)

			if not self._sess:
				err_msg = 'Could not connect to outgoing email server'
				frappe.msgprint(err_msg)
				raise frappe.OutgoingEmailError(err_msg)

			if self.use_tls:
				self._sess.ehlo()
				self._sess.starttls()
				self._sess.ehlo()

			if self.login and self.password:
				ret = self._sess.login(str(self.login or ""), str(self.password or ""))

				# check if logged correctly
				if ret[0]!=235:
					frappe.msgprint(ret[1])
					raise frappe.OutgoingEmailError(ret[1])

			return self._sess

		except _socket.error as e:
			# Invalid mail server -- due to refusing connection
			frappe.msgprint('Invalid Outgoing Mail Server or Port')
			traceback = sys.exc_info()[2]
			raise_(frappe.ValidationError, e, traceback)

		except smtplib.SMTPAuthenticationError as e:
			frappe.msgprint("Invalid login or password")
			traceback = sys.exc_info()[2]
			raise_(frappe.ValidationError, e, traceback)

		except smtplib.SMTPException:
			frappe.msgprint('Unable to send emails at this time')
			raise

patch('from frappe.email.smtp import SMTPServer', 'SMTPServer', PatchedSMTPServer)
frappe.email.smtp.SMTPServer = PatchedSMTPServer
