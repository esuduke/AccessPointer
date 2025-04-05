import win32com.client

class EmailSender:

    # Send an email via Outlook
    def send_email(self, recipient, subject, body):
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)
            mail.To = recipient
            mail.Subject = subject
            mail.Body = body
            mail.send()
            print("Email sent Successfully!")
        except Exception as e:
            print(f"Error sending email: {e}")


