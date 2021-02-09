"""Sends an email with Google API

Usage: send_email_googleapi.py [options] [--param=KEY:VALUE ...] CREDENTIALS TOKEN_FILE TO

Arguments:
    CREDENTIALS     Google API JSON credential file
    TOKEN_FILE      The file token.pickle stores the user's access and refresh tokens, and is
                    created automatically when the authorization flow completes for the first
                    time.
    TO              email list separated by ','

Options:
    --scopes=SCOPES                    If modifying these scopes, delete the file token.pickle.
    --subject=SUBJECT                  email subject
    --email-template=EMAIL_TEMPLATE    email file template to send
    --image-directory=IMAGE_DIRECTORY  folder containing images to attach with email
    --param=KEY:VALUE                  params passed to the email template to be replaced
    --content=CONTENT                  body message to send in case an EMAIL_TEMPLATE is not specified

"""
# Ex: python send_email_googleapi.py --subject="send_email.py" --email-template=template/tibero_template.html    --image-directory=template/images --param=name:"Joan Prat" --param=db_user:sys --param=db_password:1q2w·E$R    --param=db_server:sqlaas0.dimensigon.com --param=db_port:8176 --param=db_name:tibero credentials.json token.pickle    joan.prat@knowtrade.eu
import ast
import base64
import mimetypes
import os
import pickle
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from docopt import docopt
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from jinja2 import Template

BASE_DIR = os.path.dirname(os.path.realpath(__file__))


def get_gmail_service(credentials, token_pickle, scopes):
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(token_pickle):
        with open(token_pickle, 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials, scopes)
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open(token_pickle, 'wb') as token:
            pickle.dump(creds, token)

    service = build('gmail', 'v1', credentials=creds)

    return service


def create_message(sender, to, subject, message_text, image_directory=None):
    """Create a message for an email.

    Args:
      sender: Email address of the sender.
      to: Email address of the receiver.
      subject: The subject of the email message.
      message_text: The text of the email message.

    Returns:
      An object containing a base64url encoded email object.
    """
    message = MIMEMultipart()
    message['to'] = to if isinstance(to, str) else ','.join(to)
    if sender:
        message['from'] = sender
    message['subject'] = subject

    msg = MIMEText(message_text, 'html')
    message.attach(msg)

    if image_directory:
        for image_name in os.listdir(image_directory):
            with open(os.path.join(image_directory, image_name), 'rb') as img_data:
                content_type, encoding = mimetypes.guess_type(image_name)

                if content_type is None or encoding is not None:
                    content_type = 'application/octet-stream'
                main_type, sub_type = content_type.split('/', 1)
                if main_type == 'image':
                    msg = MIMEImage(img_data.read(), _subtype=sub_type)
                else:
                    msg = MIMEBase(main_type, sub_type)
                    msg.set_payload(img_data.read())

                msg.add_header('Content-Id', '<' + image_name.split('.')[0] + '>')  # angle brackets are important
                message.attach(msg)

    # https://www.pronoy.in/2016/10/20/python-3-5-x-base64-encoding-3/
    return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode('ascii')}


if __name__ == '__main__':

    # START Parse & Set Input Data
    args = docopt(__doc__)

    if args['--scopes']:
        scopes = args['--scopes'].split(',')
    else:
        scopes = ['https://www.googleapis.com/auth/gmail.readonly',
                  'https://mail.google.com/']

    params = {}
    for param in args.get('--param') or []:
        if ':' in param:
            key, value = param.split(':', 1)
            try:
                params[key] = ast.literal_eval(value)
            except:
                params[key] = value

    if args['--email-template']:
        with open(args['--email-template']) as file_:
            template = Template(file_.read())

        content = template.render(**params)
    elif args['--content']:
        content = args['--content']
    else:
        content = ''
    # END Parse & Set Input Data

    gmail_service = get_gmail_service(args['CREDENTIALS'], args['TOKEN_FILE'], scopes)
    message = create_message(None, args['TO'], args['--subject'], content, args['--image-directory'])
    message_id = (gmail_service.users().messages().send(userId='me', body=message).execute())
    print(f"sent message: {message_id}")
