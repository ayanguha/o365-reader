import datetime
import logging
import os
import pytz

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


from O365 import Account
from O365.utils import AWSS3Backend
import boto3

APP_ID="451e13a1-5367-4c83-ba0c-3a1d5583f100"
SECRET="M2N7Q~yIhutMiPIYMFIIfEvvoHaMIr5Frb.Sq"

TENAND_ID="1cabbed0-2d14-43cf-9b61-b2a8803eda0b"
resource="ayan@redclock.onmicrosoft.com"
MAX_SIZE=1000
INBOUND='inbound'
S3_BUCKET = os.environ['S3_BUCKET']
S3_TOKEN_FILENAME = os.environ['S3_TOKEN_FILENAME']

client = boto3.client('s3')


def eval_new_msg(mailbox, high_watermark_date):
    new_msgs = []
    for message in mailbox.get_messages(limit=MAX_SIZE, order_by='receivedDateTime desc', download_attachments=True):
        rd = message.received
        if rd > high_watermark_date:
            new_msgs.append(message)
    sorted_lst = sorted(new_msgs, key=lambda x: x.received)
    return sorted_lst

def get_high_watermark():
    try:
        hwm = client.get_object(
                        Bucket=S3_BUCKET,
                        Key="audit/last_modified.txt"
                    )
        td = hwm['Body'].read().decode('utf-8')
        hwmd = datetime.datetime.strptime(td, '%Y-%m-%d %H:%M:%S%z')
    except:
        hwmd = datetime.datetime.now(pytz.utc)
    return hwmd

def save_high_watermark(hwmd):
    r = client.put_object(
                    ACL='private',
                    Bucket=S3_BUCKET,
                    Key="audit/last_modified.txt",
                    Body=hwmd.strftime('%Y-%m-%d %H:%M:%S%z'),
                    ContentType='text/plain'
                )

def get_mailbox():
    credentials = (APP_ID, SECRET)
    token_backend = AWSS3Backend(S3_BUCKET, S3_TOKEN_FILENAME)
    account = Account(credentials, auth_flow_type='credentials', tenant_id=TENAND_ID,token_backend=token_backend)
    account.authenticate()
    mailbox = account.mailbox(resource=resource)

    return mailbox

def save_attachment_s3(attachment):
    local_file_name = os.path.join('/tmp', attachment.name)
    S3_Key = os.path.join(INBOUND, attachment.name)
    attachment.save(location='/tmp')
    client.upload_file(local_file_name,S3_BUCKET, S3_Key)
    return attachment.name

def download_attachments():
    hwmd = get_high_watermark()
    mailbox = get_mailbox()
    inbox = mailbox.inbox_folder()
    nm = eval_new_msg(inbox, hwmd)
    for m in nm:

        if m.has_attachments:
            for att in m.attachments:
                try:
                    saved = save_attachment_s3(att)
                    hwmd = m.received

                except:
                    raise
    s = save_high_watermark(hwmd)

def run(event, context):
    current_time = datetime.datetime.now().time()
    name = context.function_name
    logger.info("Your cron function " + name + " ran at " + str(current_time))
    download_attachments()

#download_attachments()
