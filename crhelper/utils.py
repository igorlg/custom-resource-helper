
import json
import logging as logging
import ssl
import time
from http.client import HTTPSConnection
from os import path
from typing import AnyStr
from urllib.parse import urlsplit, urlunsplit

logger = logging.getLogger(__name__)
MAX_RETRIES = 5  # Maximum number of retries

def _send_response(response_url: AnyStr, response_body: AnyStr, ssl_verify: bool | AnyStr = None):
    try:
        json_response_body = json.dumps(response_body)
    except Exception as e:
        msg = f"Failed to convert response to json: {str(e)}"
        logger.error(msg, exc_info=True)
        response_body = {'Status': 'FAILED', 'Data': {}, 'Reason': msg}
        json_response_body = json.dumps(response_body)
    logger.debug(f"CFN response URL: {response_url}")
    logger.debug(json_response_body)
    headers = {'content-type': '', 'content-length': str(len(json_response_body))}
    split_url = urlsplit(response_url)
    host = split_url.netloc
    url = urlunsplit(("", "", *split_url[2:]))
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    if isinstance(ssl_verify, str):
        if path.exists(ssl_verify):
            ctx.load_verify_locations(cafile=ssl_verify)
        else:
            logger.warning(f"Cert path {ssl_verify} does not exist!.  Falling back to using system cafile.")
    if ssl_verify is False:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    # If ssl_verify is True or None dont modify the context in any way.

    retry_count = 0
    success = False
    while retry_count < MAX_RETRIES and not success:
        try:
            connection = HTTPSConnection(host, context=ctx)
            connection.request(method="PUT", url=url, body=json_response_body, headers=headers)
            response = connection.getresponse()
            logger.info(f"CloudFormation returned status code: {response.reason}")
            success = True
        except Exception as e:
            retry_count += 1
            logger.error(f"Unexpected failure sending response to CloudFormation {e}. Retrying in 2 seconds...", exc_info=True)
            time.sleep(2)
    if not success:
        logger.error("Maximum retries reached. Unable to send response to CloudFormation.")
